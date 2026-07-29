import { h } from 'vue'

const baseProps = {
  viewBox: '0 0 40 40',
  fill: 'none',
  xmlns: 'http://www.w3.org/2000/svg',
  'aria-hidden': 'true',
}

const strokeProps = {
  stroke: 'currentColor',
  'stroke-width': 2.45,
  'stroke-linecap': 'round',
  'stroke-linejoin': 'round',
}

const fineStrokeProps = {
  ...strokeProps,
  'stroke-width': 1.75,
  opacity: 0.78,
}

const makeIcon = (name, children) => ({
  name,
  render() {
    return h('svg', baseProps, [
      h('g', { transform: 'translate(20 20) scale(1.14) translate(-20 -20)' }, children),
    ])
  },
})

const path = (d, props = strokeProps) => h('path', { d, ...props })
const rect = (props, extra = strokeProps) => h('rect', { ...props, ...extra })
const circle = (props, extra = strokeProps) => h('circle', { ...props, ...extra })
const ellipse = (props, extra = strokeProps) => h('ellipse', { ...props, ...extra })

export const SystemOverviewIcon = makeIcon('SystemOverviewIcon', [
  path('M8 25.5V15.8L20 7l12 8.8v9.7'),
  path('M13 27.5h14M15 32h10M17 25v-6h6v6', fineStrokeProps),
  path('M11.5 18.5H15M25 18.5h3.5', fineStrokeProps),
])

export const RealtimeMonitorIcon = makeIcon('RealtimeMonitorIcon', [
  rect({ x: 7, y: 10, width: 26, height: 17, rx: 2.5 }),
  path('M14 31h12M20 27v4', fineStrokeProps),
  path('M12.5 20h4l2-4.5 3.5 9 2.2-4.5h3.3'),
])

export const AlarmTriangleIcon = makeIcon('AlarmTriangleIcon', [
  path('M20 8 33 31H7L20 8Z'),
  path('M20 16v7'),
  path('M20 27.8h.1'),
  path('M13 30.8h14', fineStrokeProps),
])

export const DocumentSheetIcon = makeIcon('DocumentSheetIcon', [
  path('M12 7h12l5 5v21H12z'),
  path('M24 7v6h5M16 18h10M16 23h10M16 28h7', fineStrokeProps),
])

export const UserOperatorIcon = makeIcon('UserOperatorIcon', [
  circle({ cx: 20, cy: 15, r: 5 }),
  path('M10.5 31c1.8-5 5.4-7.5 9.5-7.5S27.7 26 29.5 31'),
  path('M31.5 13.5h2.8M32.9 12.1v2.8', fineStrokeProps),
])

export const SensorChipIcon = makeIcon('SensorChipIcon', [
  rect({ x: 14, y: 11, width: 12, height: 18, rx: 3 }),
  path('M10 15h4M10 20h4M10 25h4M26 15h4M26 20h4M26 25h4', fineStrokeProps),
  path('M18 8v3M22 8v3M18 29v3M22 29v3', fineStrokeProps),
  path('M18 17h4M18 22h4'),
])

export const VideoMonitorIcon = makeIcon('VideoMonitorIcon', [
  rect({ x: 8, y: 12, width: 19, height: 16, rx: 3 }),
  path('M27 17.5 33 14v12l-6-3.5'),
  path('M14 30h9M18.5 28v2', fineStrokeProps),
])

export const PlatformUptimeIcon = makeIcon('PlatformUptimeIcon', [
  rect({ x: 10, y: 13, width: 20, height: 18, rx: 4 }),
  path('M15 9v4M25 9v4M14.5 18h11', fineStrokeProps),
  path('M20 22v4l3 1.8'),
])

export const HostUptimeIcon = makeIcon('HostUptimeIcon', [
  circle({ cx: 20, cy: 20, r: 11 }),
  path('M20 14v7h6'),
  path('M20 5.8v3M20 31.2v3M5.8 20h3M31.2 20h3', fineStrokeProps),
])

export const CpuLoadIcon = makeIcon('CpuLoadIcon', [
  rect({ x: 12, y: 12, width: 16, height: 16, rx: 3 }),
  rect({ x: 16, y: 16, width: 8, height: 8, rx: 1.5 }, fineStrokeProps),
  path('M9 15h3M9 20h3M9 25h3M28 15h3M28 20h3M28 25h3M15 9v3M20 9v3M25 9v3M15 28v3M20 28v3M25 28v3', fineStrokeProps),
])

export const MemoryModuleIcon = makeIcon('MemoryModuleIcon', [
  rect({ x: 9, y: 13, width: 22, height: 14, rx: 3 }),
  path('M13 17h4v6h-4zM19 17h4v6h-4zM25 17h2', fineStrokeProps),
  path('M12 10v3M17 10v3M22 10v3M27 10v3M12 27v3M17 27v3M22 27v3M27 27v3', fineStrokeProps),
])

export const GpuBoardIcon = makeIcon('GpuBoardIcon', [
  path('M9 14h18a4 4 0 0 1 4 4v4a4 4 0 0 1-4 4H9z'),
  path('M13 18h7v4h-7zM31 18h3v4h-3M11 11v18', fineStrokeProps),
  path('M22 18.2c2.8.7 4.4 2.3 5 4.8'),
])

export const StorageStackIcon = makeIcon('StorageStackIcon', [
  ellipse({ cx: 20, cy: 12, rx: 10, ry: 4 }),
  path('M10 12v16c0 2.2 4.5 4 10 4s10-1.8 10-4V12'),
  path('M10 20c0 2.2 4.5 4 10 4s10-1.8 10-4M10 26c0 2.2 4.5 4 10 4s10-1.8 10-4', fineStrokeProps),
])

export const EdgeCollectorIcon = makeIcon('EdgeCollectorIcon', [
  rect({ x: 8, y: 13, width: 10, height: 10, rx: 2 }),
  rect({ x: 22, y: 17, width: 10, height: 10, rx: 2 }),
  path('M18 18h4M15 23v3.5c0 1.4 1.1 2.5 2.5 2.5H22'),
  path('M12 10v3M27 27v3M6 18h2M32 22h2', fineStrokeProps),
])

export const AiInferenceIcon = makeIcon('AiInferenceIcon', [
  circle({ cx: 20, cy: 20, r: 9 }),
  path('M20 11V7M20 33v-4M11 20H7M33 20h-4'),
  path('M16 22c1.1 1.6 2.4 2.4 4 2.4s2.9-.8 4-2.4M16.8 17.2h.1M23.1 17.2h.1', fineStrokeProps),
])
