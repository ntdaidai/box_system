<template>
  <div class="knowledge-base">
    <section class="kb-command">
      <div class="kb-copy">
        <span class="kb-kicker">INTELLIGENT DATA HUB</span>
        <h1>知识库</h1>
        <p>汇聚巡查报告、监测规范、历史告警和处置经验，形成可检索、可问答、可追溯的坝区智能知识中台。</p>
      </div>
      <div class="kb-orchestrator" aria-label="知识库能力概览">
        <div
          v-for="metric in metrics"
          :key="metric.label"
          class="kb-metric"
        >
          <el-icon><component :is="metric.icon" /></el-icon>
          <span>{{ metric.label }}</span>
          <strong>{{ metric.value }}</strong>
        </div>
      </div>
    </section>

    <section class="kb-search-band">
      <div class="semantic-input">
        <el-icon><Search /></el-icon>
        <input v-model="question" type="text" placeholder="搜索知识、提问告警处置方案、查询巡查依据..." />
      </div>
      <el-button type="primary" class="ask-button">
        <el-icon><MagicStick /></el-icon>
        智能问答
      </el-button>
      <el-button class="index-button">
        <el-icon><Upload /></el-icon>
        导入知识
      </el-button>
    </section>

    <div class="kb-layout">
      <section class="kb-panel knowledge-map">
        <div class="panel-title">
          <div>
            <span>知识网络</span>
            <small>Document + Event + Sensor + Action</small>
          </div>
          <el-tag effect="dark" type="success">架构设计</el-tag>
        </div>
        <div class="graph-stage">
          <span class="graph-link link-doc"></span>
          <span class="graph-link link-rule"></span>
          <span class="graph-link link-event"></span>
          <span class="graph-link link-action"></span>
          <div class="graph-core">
            <el-icon><Collection /></el-icon>
            <strong>坝区知识中枢</strong>
            <span>可信问答 / 引用溯源</span>
          </div>
          <div
            v-for="domain in domains"
            :key="domain.name"
            class="graph-node"
            :class="domain.className"
          >
            <el-icon><component :is="domain.icon" /></el-icon>
            <div>
              <strong>{{ domain.name }}</strong>
              <span>{{ domain.desc }}</span>
            </div>
          </div>
        </div>
      </section>

      <section class="kb-panel pipeline-panel">
        <div class="panel-title">
          <div>
            <span>知识入库流水线</span>
            <small>从文件到可问答知识</small>
          </div>
          <el-icon><Operation /></el-icon>
        </div>
        <div class="pipeline">
          <div
            v-for="step in pipeline"
            :key="step.name"
            class="pipeline-item"
          >
            <div class="pipeline-icon">
              <el-icon><component :is="step.icon" /></el-icon>
            </div>
            <div class="pipeline-copy">
              <strong>{{ step.name }}</strong>
              <span>{{ step.desc }}</span>
            </div>
            <em>{{ step.state }}</em>
          </div>
        </div>
      </section>

      <section class="kb-panel qa-panel">
        <div class="panel-title">
          <div>
            <span>智能问答预览</span>
            <small>答案必须带来源</small>
          </div>
          <el-icon><ChatLineRound /></el-icon>
        </div>
        <div class="answer-preview">
          <div class="question-chip">坝体渗压异常时优先排查什么？</div>
          <div class="answer-card">
            <p>优先核对传感器最近 24 小时趋势、雨量变化、巡查记录和历史处置单，并给出可执行排查顺序。</p>
            <div class="source-row">
              <span>引用：巡查日报</span>
              <span>引用：监测规范</span>
            </div>
          </div>
        </div>
      </section>

      <section class="kb-panel capability-panel">
        <div class="panel-title">
          <div>
            <span>能力矩阵</span>
            <small>智能数据中台基础能力</small>
          </div>
          <el-icon><TrendCharts /></el-icon>
        </div>
        <div class="capability-grid">
          <div v-for="item in capabilities" :key="item.name">
            <span>{{ item.name }}</span>
            <strong>{{ item.value }}</strong>
          </div>
        </div>
      </section>

    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import {
  ChatLineRound,
  Collection,
  Cpu,
  DataAnalysis,
  Document,
  Files,
  MagicStick,
  Operation,
  Reading,
  Search,
  Share,
  TrendCharts,
  Upload,
} from '@element-plus/icons-vue'

const question = ref('')

const metrics = [
  { label: '文档资产', value: 'DOC', icon: Files },
  { label: '知识索引', value: 'RAG', icon: Cpu },
  { label: '引用溯源', value: 'TRACE', icon: Share },
]

const domains = [
  { name: '巡查报告', desc: '日报、月报、专项检查', icon: Reading, className: 'node-doc' },
  { name: '监测规范', desc: '阈值、制度、处置标准', icon: Document, className: 'node-rule' },
  { name: '历史告警', desc: '事件、等级、处置过程', icon: DataAnalysis, className: 'node-event' },
  { name: '处置经验', desc: '预案、任务、复盘结论', icon: Share, className: 'node-action' },
]

const pipeline = [
  { name: '解析', desc: '提取正文、表格、图片说明和元数据', state: '待接入', icon: Files },
  { name: '切片', desc: '按章节、语义和业务对象拆分知识片段', state: '待接入', icon: Operation },
  { name: '索引', desc: '写入全文索引和向量索引，保留来源', state: '待接入', icon: Cpu },
  { name: '问答', desc: '检索增强生成，答案绑定原文证据', state: '待接入', icon: MagicStick },
]

const capabilities = [
  { name: '语义检索', value: 'Hybrid' },
  { name: '权限继承', value: 'RBAC' },
  { name: '答案来源', value: '段落级' },
  { name: '增量更新', value: '实时' },
]

</script>

<style scoped>
.knowledge-base {
  min-height: 100%;
  padding: 20px;
  color: #e7f3ff;
}

.kb-command {
  display: grid;
  grid-template-columns: minmax(0, 1.45fr) minmax(360px, 0.8fr);
  gap: 18px;
  margin-bottom: 16px;
  padding: 24px;
  overflow: hidden;
  background:
    linear-gradient(135deg, rgba(8, 27, 47, 0.98), rgba(16, 50, 73, 0.9)),
    radial-gradient(circle at 80% 14%, rgba(51, 218, 186, 0.22), transparent 34%);
  border: 1px solid rgba(91, 191, 232, 0.34);
  border-radius: 8px;
  box-shadow: 0 18px 46px rgba(0, 0, 0, 0.24);
}

.kb-copy {
  min-width: 0;
}

.kb-kicker {
  display: inline-flex;
  align-items: center;
  height: 24px;
  padding: 0 10px;
  color: #7ae9ff;
  background: rgba(122, 233, 255, 0.1);
  border: 1px solid rgba(122, 233, 255, 0.26);
  border-radius: 4px;
  font-size: 12px;
  font-weight: 800;
}

.kb-copy h1 {
  margin: 10px 0 8px;
  color: #f7fbff;
  font-size: 30px;
  font-weight: 800;
  letter-spacing: 0;
}

.kb-copy p {
  max-width: 760px;
  margin: 0;
  color: #b8cce4;
  font-size: 14px;
  line-height: 1.7;
}

.kb-orchestrator {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 10px;
}

.kb-metric {
  display: flex;
  min-width: 0;
  min-height: 120px;
  flex-direction: column;
  justify-content: space-between;
  padding: 14px;
  background: rgba(5, 19, 34, 0.58);
  border: 1px solid rgba(119, 190, 226, 0.22);
  border-radius: 8px;
}

.kb-metric .el-icon {
  color: #75e8ff;
  font-size: 24px;
}

.kb-metric span {
  color: #a9c2dc;
  font-size: 13px;
}

.kb-metric strong {
  color: #fff;
  font-size: 24px;
  font-weight: 800;
}

.kb-search-band {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto auto;
  gap: 10px;
  align-items: center;
  margin-bottom: 16px;
  padding: 12px;
  background: rgba(11, 31, 52, 0.82);
  border: 1px solid rgba(91, 191, 232, 0.24);
  border-radius: 8px;
}

.semantic-input {
  display: flex;
  align-items: center;
  gap: 10px;
  min-width: 0;
  height: 46px;
  padding: 0 14px;
  background: rgba(4, 18, 32, 0.76);
  border: 1px solid rgba(107, 178, 220, 0.22);
  border-radius: 6px;
}

.semantic-input .el-icon {
  flex: 0 0 auto;
  color: #75e8ff;
}

.semantic-input input {
  min-width: 0;
  width: 100%;
  color: #ecf7ff;
  background: transparent;
  border: 0;
  outline: 0;
  font-size: 14px;
}

.semantic-input input::placeholder {
  color: #85a5c4;
}

.ask-button,
.index-button {
  height: 46px;
  min-width: 118px;
  font-weight: 800;
}

.index-button {
  color: #dcefff;
  background: rgba(122, 233, 255, 0.08);
  border-color: rgba(122, 233, 255, 0.26);
}

.kb-layout {
  display: grid;
  grid-template-columns: minmax(440px, 1.25fr) minmax(320px, 0.8fr);
  gap: 16px;
}

.kb-panel {
  min-width: 0;
  padding: 18px;
  background: rgba(13, 37, 62, 0.84);
  border: 1px solid rgba(96, 177, 224, 0.24);
  border-radius: 8px;
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.04);
}

.knowledge-map {
  grid-row: span 3;
}

.panel-title {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 16px;
}

.panel-title span {
  display: block;
  color: #eef8ff;
  font-size: 16px;
  font-weight: 800;
}

.panel-title small {
  display: block;
  margin-top: 4px;
  color: #89a7c4;
  font-size: 12px;
}

.panel-title .el-icon {
  color: #75e8ff;
  font-size: 21px;
}

.graph-stage {
  position: relative;
  min-height: 560px;
  overflow: hidden;
  background:
    linear-gradient(rgba(111, 183, 230, 0.08) 1px, transparent 1px),
    linear-gradient(90deg, rgba(111, 183, 230, 0.08) 1px, transparent 1px);
  background-size: 34px 34px;
  border: 1px solid rgba(104, 174, 220, 0.16);
  border-radius: 8px;
}

.graph-core {
  position: absolute;
  z-index: 2;
  top: 50%;
  left: 50%;
  display: flex;
  width: 184px;
  min-height: 112px;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 8px;
  color: #061b2c;
  text-align: center;
  background: linear-gradient(135deg, #86f1ff, #82f3bf);
  border: 1px solid rgba(255, 255, 255, 0.65);
  border-radius: 8px;
  box-shadow: 0 18px 36px rgba(0, 0, 0, 0.3);
  transform: translate(-50%, -50%);
}

.graph-core .el-icon {
  font-size: 26px;
}

.graph-core strong {
  font-size: 15px;
  font-weight: 900;
}

.graph-core span {
  font-size: 12px;
  font-weight: 700;
}

.graph-node {
  position: absolute;
  z-index: 2;
  display: grid;
  grid-template-columns: 34px minmax(0, 1fr);
  gap: 10px;
  align-items: center;
  width: 190px;
  min-height: 72px;
  padding: 12px;
  color: #eaf7ff;
  background: rgba(10, 42, 70, 0.96);
  border: 1px solid rgba(122, 233, 255, 0.35);
  border-radius: 8px;
  box-shadow: 0 14px 28px rgba(0, 0, 0, 0.24);
}

.graph-node .el-icon {
  color: #7ae9ff;
  font-size: 24px;
}

.graph-node strong,
.graph-node span {
  display: block;
}

.graph-node strong {
  color: #f6fbff;
  font-size: 14px;
  font-weight: 800;
}

.graph-node span {
  margin-top: 4px;
  color: #9fb9d3;
  font-size: 12px;
  line-height: 1.4;
}

.node-doc { top: 13%; left: 8%; }
.node-rule { top: 14%; right: 8%; }
.node-event { bottom: 16%; left: 10%; }
.node-action { right: 10%; bottom: 15%; }

.graph-link {
  position: absolute;
  z-index: 1;
  top: 50%;
  left: 50%;
  width: 35%;
  height: 1px;
  background: linear-gradient(90deg, rgba(122, 233, 255, 0.04), rgba(122, 233, 255, 0.58));
  transform-origin: left center;
}

.link-doc { transform: rotate(220deg); }
.link-rule { transform: rotate(320deg); }
.link-event { transform: rotate(142deg); }
.link-action { transform: rotate(38deg); }

.pipeline {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.pipeline-item {
  display: grid;
  grid-template-columns: 42px minmax(0, 1fr) auto;
  gap: 12px;
  align-items: center;
  min-height: 64px;
  padding: 10px 12px;
  background: rgba(5, 19, 34, 0.46);
  border: 1px solid rgba(104, 174, 220, 0.14);
  border-radius: 8px;
}

.pipeline-icon {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 42px;
  height: 42px;
  color: #86f1ff;
  background: rgba(122, 233, 255, 0.1);
  border-radius: 8px;
}

.pipeline-copy strong,
.pipeline-copy span {
  display: block;
}

.pipeline-copy strong {
  color: #f2f9ff;
  font-size: 14px;
  font-weight: 800;
}

.pipeline-copy span {
  margin-top: 4px;
  color: #9db7d2;
  font-size: 12px;
  line-height: 1.45;
}

.pipeline-item em {
  display: inline-flex;
  align-items: center;
  height: 26px;
  padding: 0 10px;
  color: #82f3bf;
  background: rgba(130, 243, 191, 0.1);
  border: 1px solid rgba(130, 243, 191, 0.22);
  border-radius: 4px;
  font-size: 12px;
  font-style: normal;
  font-weight: 800;
}

.answer-preview {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.question-chip {
  align-self: flex-start;
  max-width: 92%;
  padding: 10px 12px;
  color: #07192a;
  background: #86f1ff;
  border-radius: 8px 8px 8px 2px;
  font-size: 13px;
  font-weight: 800;
}

.answer-card {
  padding: 14px;
  background: rgba(5, 19, 34, 0.46);
  border: 1px solid rgba(104, 174, 220, 0.14);
  border-radius: 8px;
}

.answer-card p {
  margin: 0;
  color: #c7daec;
  font-size: 13px;
  line-height: 1.7;
}

.source-row {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 12px;
}

.source-row span {
  display: inline-flex;
  align-items: center;
  height: 26px;
  padding: 0 9px;
  color: #ffe39b;
  background: rgba(255, 227, 155, 0.1);
  border: 1px solid rgba(255, 227, 155, 0.24);
  border-radius: 4px;
  font-size: 12px;
  font-weight: 800;
}

.capability-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
}

.capability-grid div {
  min-height: 78px;
  padding: 14px;
  background: rgba(5, 19, 34, 0.46);
  border: 1px solid rgba(104, 174, 220, 0.14);
  border-radius: 8px;
}

.capability-grid span {
  display: block;
  color: #9db7d2;
  font-size: 13px;
}

.capability-grid strong {
  display: block;
  margin-top: 10px;
  color: #f7fbff;
  font-size: 20px;
  font-weight: 800;
}

@media (max-width: 920px) {
  .kb-command,
  .kb-search-band,
  .kb-layout {
    grid-template-columns: 1fr;
  }

  .kb-orchestrator {
    grid-template-columns: 1fr;
  }

  .ask-button,
  .index-button {
    width: 100%;
  }

  .knowledge-map {
    grid-row: auto;
  }

  .graph-stage {
    min-height: 430px;
  }

  .graph-node {
    width: 152px;
    grid-template-columns: 1fr;
    text-align: center;
  }

  .pipeline-item {
    grid-template-columns: 1fr;
  }

  .pipeline-icon {
    display: none;
  }

  .capability-grid {
    grid-template-columns: 1fr;
  }
}
</style>
