<template>
  <Teleport to="body">
    <Transition name="app-dialog-fade" @after-leave="handleClosed">
      <div
        v-if="modelValue"
        class="app-dialog-layer"
        :style="layerStyle"
        @mousedown.self="handleMaskMouseDown"
        @click.self="handleMaskClick"
      >
        <section
          ref="panelRef"
          class="app-dialog-panel"
          :class="{ 'is-fullscreen': fullscreen, 'is-top-aligned': hasTopOffset }"
          :style="panelStyle"
          role="dialog"
          aria-modal="true"
          :aria-label="title || '对话框'"
          tabindex="-1"
          v-bind="$attrs"
          @click.stop
        >
          <header v-if="$slots.header || title || showClose" class="app-dialog__header">
            <template v-if="$slots.header">
              <slot name="header" />
            </template>
            <template v-else>
              <h2 v-if="title" class="app-dialog__title">{{ title }}</h2>
              <span v-else class="app-dialog__title-spacer" aria-hidden="true"></span>
              <button
                v-if="showClose"
                class="app-dialog__close"
                type="button"
                aria-label="关闭弹窗"
                @click="requestClose"
              >
                <span aria-hidden="true"></span>
              </button>
            </template>
          </header>

          <div class="app-dialog__body">
            <slot />
          </div>

          <footer v-if="$slots.footer" class="app-dialog__footer">
            <slot name="footer" />
          </footer>
        </section>
      </div>
    </Transition>
  </Teleport>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, ref, watch } from 'vue'

defineOptions({ inheritAttrs: false })

const props = defineProps({
  modelValue: { type: Boolean, default: false },
  title: { type: String, default: '' },
  width: { type: [String, Number], default: '560px' },
  top: { type: String, default: '' },
  fullscreen: { type: Boolean, default: false },
  alignCenter: { type: Boolean, default: false },
  showClose: { type: Boolean, default: true },
  closeOnClickModal: { type: Boolean, default: true },
  closeOnPressEscape: { type: Boolean, default: true },
  appendToBody: { type: Boolean, default: true },
  destroyOnClose: { type: Boolean, default: true },
  zIndex: { type: [String, Number], default: 3400 },
})

const emit = defineEmits(['update:modelValue', 'open', 'opened', 'close', 'closed'])
const panelRef = ref(null)
let previousFocus = null
let maskPressed = false

const hasTopOffset = computed(() => !props.fullscreen && Boolean(props.top) && !props.alignCenter)
const resolvedWidth = computed(() => (typeof props.width === 'number' ? `${props.width}px` : props.width))
const layerStyle = computed(() => ({ zIndex: props.zIndex }))
const panelStyle = computed(() => {
  if (props.fullscreen) return {}
  return {
    width: resolvedWidth.value,
    marginTop: hasTopOffset.value ? props.top : undefined,
  }
})

watch(
  () => props.modelValue,
  (visible) => {
    if (visible) {
      previousFocus = document.activeElement instanceof HTMLElement ? document.activeElement : null
      document.addEventListener('keydown', handleKeydown)
      nextTick(() => {
        panelRef.value?.focus()
        emit('open')
        emit('opened')
      })
      return
    }
    document.removeEventListener('keydown', handleKeydown)
  },
  { immediate: true },
)

onBeforeUnmount(() => document.removeEventListener('keydown', handleKeydown))

function handleKeydown(event) {
  if (event.key === 'Escape' && props.closeOnPressEscape) {
    event.preventDefault()
    requestClose()
  }
}

function handleMaskMouseDown() {
  maskPressed = true
}

function handleMaskClick() {
  if (maskPressed && props.closeOnClickModal) requestClose()
  maskPressed = false
}

function requestClose() {
  emit('close')
  emit('update:modelValue', false)
}

function handleClosed() {
  previousFocus?.focus?.()
  previousFocus = null
  emit('closed')
}
</script>

<style>
.app-dialog-layer {
  position: fixed;
  inset: 0;
  display: grid;
  place-items: center;
  padding: clamp(12px, 2vw, 32px);
  overflow: auto;
  background: rgba(1, 9, 18, .7);
  backdrop-filter: blur(5px);
}

.app-dialog-panel {
  --dialog-border: rgba(77, 184, 234, .42);
  --dialog-muted: #87afc9;
  width: min(560px, calc(100vw - 24px));
  max-width: calc(100vw - 24px);
  max-height: calc(100vh - 24px);
  min-width: 0;
  min-height: 0;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  color: #eaf7ff;
  border: 1px solid var(--dialog-border);
  border-radius: 12px;
  background: linear-gradient(180deg, #0b2841 0%, #061a2d 100%);
  box-shadow: 0 24px 70px rgba(0, 0, 0, .52), inset 0 1px 0 rgba(214, 244, 255, .07);
  outline: none;
}

.app-dialog-panel.is-top-aligned {
  align-self: start;
}

.app-dialog-panel.is-fullscreen {
  width: 100vw !important;
  max-width: 100vw;
  height: 100vh;
  max-height: 100vh;
  border: 0;
  border-radius: 0;
}

.app-dialog__header {
  min-height: 58px;
  display: flex;
  align-items: center;
  gap: 14px;
  padding: 0 16px 0 20px;
  border-bottom: 1px solid rgba(103, 184, 226, .18);
  background: linear-gradient(90deg, rgba(19, 67, 101, .78), rgba(7, 30, 50, .5));
}

.app-dialog__header > :only-child {
  min-width: 0;
  flex: 1 1 auto;
}

.app-dialog__title,
.app-dialog__title-spacer {
  min-width: 0;
  margin: 0;
  flex: 1;
}

.app-dialog__title {
  overflow: hidden;
  color: #f2fbff;
  font-size: clamp(17px, 1.1vw, 20px);
  font-weight: 700;
  line-height: 1.25;
  letter-spacing: 0;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.app-dialog__close {
  width: 32px;
  height: 32px;
  flex: 0 0 auto;
  position: relative;
  display: grid;
  place-items: center;
  border: 1px solid transparent;
  border-radius: 7px;
  color: #9bc6df;
  background: transparent;
  cursor: pointer;
  transition: border-color .18s ease, background-color .18s ease, color .18s ease;
}

.app-dialog__close span,
.app-dialog__close span::before {
  width: 14px;
  height: 1.5px;
  position: absolute;
  display: block;
  border-radius: 2px;
  background: currentColor;
  content: '';
}

.app-dialog__close span { transform: rotate(45deg); }
.app-dialog__close span::before { transform: rotate(90deg); }

.app-dialog__close:hover,
.app-dialog__close:focus-visible {
  color: #f5fbff;
  border-color: rgba(102, 202, 246, .5);
  background: rgba(55, 139, 188, .16);
  outline: none;
}

.app-dialog__body {
  min-width: 0;
  min-height: 0;
  flex: 1 1 auto;
  overflow: auto;
  padding: 20px;
}

.app-dialog__footer {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 10px;
  min-height: 68px;
  padding: 12px 20px 16px;
  border-top: 1px solid rgba(103, 184, 226, .16);
  background: rgba(4, 20, 34, .42);
}

.app-dialog__footer .el-button {
  min-width: 82px;
  height: 34px;
  border-radius: 6px;
}

.app-dialog-fade-enter-active,
.app-dialog-fade-leave-active {
  transition: opacity .18s ease;
}

.app-dialog-fade-enter-active .app-dialog-panel,
.app-dialog-fade-leave-active .app-dialog-panel {
  transition: opacity .18s ease, transform .18s ease;
}

.app-dialog-fade-enter-from,
.app-dialog-fade-leave-to {
  opacity: 0;
}

.app-dialog-fade-enter-from .app-dialog-panel,
.app-dialog-fade-leave-to .app-dialog-panel {
  opacity: 0;
  transform: translateY(8px) scale(.985);
}

@media (max-width: 640px) {
  .app-dialog-layer { padding: 10px; }
  .app-dialog-panel { max-width: calc(100vw - 20px); max-height: calc(100vh - 20px); border-radius: 10px; }
  .app-dialog__header { min-height: 52px; padding: 0 12px 0 16px; }
  .app-dialog__body { padding: 16px; }
  .app-dialog__footer { min-height: 62px; padding: 10px 16px 12px; }
}
</style>
