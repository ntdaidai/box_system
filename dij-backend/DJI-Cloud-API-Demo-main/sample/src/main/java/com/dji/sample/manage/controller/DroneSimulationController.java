package com.dji.sample.manage.controller;

import com.dji.sdk.common.HttpResultResponse;
import com.fasterxml.jackson.annotation.JsonProperty;
import org.springframework.http.MediaType;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.servlet.mvc.method.annotation.SseEmitter;

import javax.validation.Valid;
import java.io.IOException;
import java.util.*;
import java.util.concurrent.*;

/**
 * 无人机模拟飞行控制器
 * 提供模拟飞行任务创建和SSE位置推送功能
 */
@RestController
@RequestMapping("${url.manage.prefix}${url.manage.version}/simulation")
public class DroneSimulationController {

    // 存储运行中的模拟任务
    private static final Map<String, SimulationTask> runningTasks = new ConcurrentHashMap<>();

    // 线程池用于执行模拟任务
    private static final ExecutorService executor = Executors.newCachedThreadPool();

    /**
     * 开始模拟飞行
     */
    @PostMapping("/start")
    public HttpResultResponse startSimulation(@Valid @RequestBody SimulationStartRequest request) {
        String jobId = request.getJobId();
        if (jobId == null || jobId.isEmpty()) {
            jobId = "sim_" + System.currentTimeMillis();
        }

        // 创建模拟任务
        SimulationTask task = new SimulationTask(jobId, request.getRouteName(),
                request.getWaypoints(), request.getDuration(), request.getStartProgress());
        runningTasks.put(jobId, task);

        // 异步执行模拟
        executor.submit(() -> executeSimulation(task));

        Map<String, Object> result = new HashMap<>();
        result.put("job_id", jobId);
        result.put("status", "started");
        return HttpResultResponse.success(result);
    }

    /**
     * SSE接口：接收无人机位置更新
     */
    @GetMapping(value = "/events/{job_id}", produces = MediaType.TEXT_EVENT_STREAM_VALUE)
    public SseEmitter streamEvents(@PathVariable("job_id") String jobId) {
        SseEmitter emitter = new SseEmitter(0L); // 不超时

        SimulationTask task = runningTasks.get(jobId);
        if (task == null) {
            try {
                emitter.send(SseEmitter.event()
                        .name("error")
                        .data("{\"error\":\"任务不存在: " + jobId + "\"}"));
                emitter.complete();
            } catch (IOException e) {
                emitter.completeWithError(e);
            }
            return emitter;
        }

        // 注册emitter
        task.addEmitter(emitter);

        // 发送初始连接确认
        try {
            emitter.send(SseEmitter.event()
                    .name("connected")
                    .data("{\"job_id\":\"" + jobId + "\",\"status\":\"connected\"}"));
        } catch (IOException e) {
            emitter.completeWithError(e);
        }

        // 设置完成和超时回调
        emitter.onCompletion(() -> task.removeEmitter(emitter));
        emitter.onTimeout(() -> task.removeEmitter(emitter));
        emitter.onError(e -> task.removeEmitter(emitter));

        return emitter;
    }

    /**
     * 获取模拟任务状态
     */
    @GetMapping("/status/{job_id}")
    public HttpResultResponse getStatus(@PathVariable("job_id") String jobId) {
        SimulationTask task = runningTasks.get(jobId);
        if (task == null) {
            return HttpResultResponse.error("任务不存在");
        }
        Map<String, Object> status = new HashMap<>();
        status.put("job_id", jobId);
        status.put("progress", task.getProgress());
        status.put("status", task.isCompleted() ? "completed" : "running");
        status.put("current_x", task.getCurrentX());
        status.put("current_y", task.getCurrentY());
        return HttpResultResponse.success(status);
    }

    /**
     * 停止模拟任务
     */
    @PostMapping("/stop/{job_id}")
    public HttpResultResponse stopSimulation(@PathVariable("job_id") String jobId) {
        SimulationTask task = runningTasks.get(jobId);
        if (task == null) {
            return HttpResultResponse.error("任务不存在");
        }
        task.stop();
        runningTasks.remove(jobId);
        return HttpResultResponse.success("已停止");
    }

    /**
     * 执行模拟飞行（在后台线程中运行）
     */
    private void executeSimulation(SimulationTask task) {
        List<Waypoint> waypoints = task.getWaypoints();
        if (waypoints == null || waypoints.size() < 2) {
            task.sendError("航点数据不足");
            task.complete();
            return;
        }

        int totalSteps = (int) (task.getDuration() / 200); // 每200ms一步
        int totalSegments = waypoints.size() - 1;
        int startStep = (int) (task.getStartProgress() * totalSteps); // 从指定进度开始

        for (int step = startStep; step <= totalSteps && !task.isStopped(); step++) {
            double progress = (double) step / totalSteps;
            int currentSegment = Math.min((int) (progress * totalSegments), totalSegments - 1);
            double segmentLocalProgress = (progress * totalSegments) - currentSegment;

            // 缓动函数
            double easedProgress = segmentLocalProgress < 0.5
                    ? 2 * segmentLocalProgress * segmentLocalProgress
                    : 1 - Math.pow(-2 * segmentLocalProgress + 2, 2) / 2;

            Waypoint from = waypoints.get(currentSegment);
            Waypoint to = waypoints.get(currentSegment + 1);

            double x = from.getX() + (to.getX() - from.getX()) * easedProgress;
            double y = from.getY() + (to.getY() - from.getY()) * easedProgress;

            task.setCurrentX(x);
            task.setCurrentY(y);
            task.setProgress(progress);

            // 发送位置更新
            Map<String, Object> data = new HashMap<>();
            data.put("x", Math.round(x * 100.0) / 100.0);
            data.put("y", Math.round(y * 100.0) / 100.0);
            data.put("progress", Math.round(progress * 10000) / 100.0);
            data.put("segment", currentSegment);
            data.put("status", step >= totalSteps ? "completed" : "flying");
            task.sendEvent("position", data);

            // 等待200ms
            try {
                Thread.sleep(200);
            } catch (InterruptedException e) {
                Thread.currentThread().interrupt();
                break;
            }
        }

        // 完成
        task.sendEvent("complete", Map.of("job_id", task.getJobId(), "status", "completed"));
        task.complete();
        runningTasks.remove(task.getJobId());
    }

    // ========== 内部类 ==========

    /**
     * 模拟任务
     */
    static class SimulationTask {
        private final String jobId;
        private final String routeName;
        private final List<Waypoint> waypoints;
        private final long duration;
        private final double startProgress;
        private final List<SseEmitter> emitters = new CopyOnWriteArrayList<>();
        private volatile double currentX;
        private volatile double currentY;
        private volatile double progress;
        private volatile boolean completed = false;
        private volatile boolean stopped = false;

        public SimulationTask(String jobId, String routeName, List<Waypoint> waypoints, long duration) {
            this(jobId, routeName, waypoints, duration, 0);
        }

        public SimulationTask(String jobId, String routeName, List<Waypoint> waypoints, long duration, double startProgress) {
            this.jobId = jobId;
            this.routeName = routeName;
            this.waypoints = waypoints;
            this.duration = duration > 0 ? duration : 60000;
            this.startProgress = Math.max(0, Math.min(1, startProgress));
            this.progress = this.startProgress;
            if (waypoints != null && !waypoints.isEmpty()) {
                this.currentX = waypoints.get(0).getX();
                this.currentY = waypoints.get(0).getY();
            }
        }

        public void addEmitter(SseEmitter emitter) { emitters.add(emitter); }
        public void removeEmitter(SseEmitter emitter) { emitters.remove(emitter); }

        public void sendEvent(String eventName, Object data) {
            String json = toJson(data);
            for (SseEmitter emitter : emitters) {
                try {
                    emitter.send(SseEmitter.event().name(eventName).data(json));
                } catch (IOException e) {
                    emitters.remove(emitter);
                }
            }
        }

        public void sendError(String message) {
            sendEvent("error", Map.of("error", message));
        }

        public void complete() {
            this.completed = true;
            for (SseEmitter emitter : emitters) {
                try { emitter.complete(); } catch (Exception ignored) {}
            }
            emitters.clear();
        }

        public void stop() {
            this.stopped = true;
            complete();
        }

        // Getters/Setters
        public String getJobId() { return jobId; }
        public String getRouteName() { return routeName; }
        public List<Waypoint> getWaypoints() { return waypoints; }
        public long getDuration() { return duration; }
        public double getStartProgress() { return startProgress; }
        public double getCurrentX() { return currentX; }
        public void setCurrentX(double x) { this.currentX = x; }
        public double getCurrentY() { return currentY; }
        public void setCurrentY(double y) { this.currentY = y; }
        public double getProgress() { return progress; }
        public void setProgress(double p) { this.progress = p; }
        public boolean isCompleted() { return completed; }
        public boolean isStopped() { return stopped; }

        private String toJson(Object obj) {
            if (obj instanceof Map) {
                Map<?, ?> map = (Map<?, ?>) obj;
                StringBuilder sb = new StringBuilder("{");
                boolean first = true;
                for (Map.Entry<?, ?> entry : map.entrySet()) {
                    if (!first) sb.append(",");
                    sb.append("\"").append(entry.getKey()).append("\":");
                    Object val = entry.getValue();
                    if (val instanceof String) {
                        sb.append("\"").append(val).append("\"");
                    } else {
                        sb.append(val);
                    }
                    first = false;
                }
                sb.append("}");
                return sb.toString();
            }
            return obj.toString();
        }
    }

    /**
     * 航点
     */
    public static class Waypoint {
        private double x;
        private double y;
        private String label;

        public Waypoint() {}
        public Waypoint(double x, double y, String label) {
            this.x = x; this.y = y; this.label = label;
        }

        public double getX() { return x; }
        public void setX(double x) { this.x = x; }
        public double getY() { return y; }
        public void setY(double y) { this.y = y; }
        public String getLabel() { return label; }
        public void setLabel(String label) { this.label = label; }
    }

    /**
     * 模拟开始请求
     */
    public static class SimulationStartRequest {
        @JsonProperty("job_id")
        private String jobId;
        @JsonProperty("route_name")
        private String routeName;
        private List<Waypoint> waypoints;
        private long duration = 60000;
        @JsonProperty("start_progress")
        private double startProgress = 0;

        public String getJobId() { return jobId; }
        public void setJobId(String jobId) { this.jobId = jobId; }
        public String getRouteName() { return routeName; }
        public void setRouteName(String routeName) { this.routeName = routeName; }
        public List<Waypoint> getWaypoints() { return waypoints; }
        public void setWaypoints(List<Waypoint> waypoints) { this.waypoints = waypoints; }
        public long getDuration() { return duration; }
        public void setDuration(long duration) { this.duration = duration; }
        public double getStartProgress() { return startProgress; }
        public void setStartProgress(double startProgress) { this.startProgress = startProgress; }
    }
}
