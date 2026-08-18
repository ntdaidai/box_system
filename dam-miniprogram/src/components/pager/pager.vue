<template>
  <view v-if="totalPages > 1" class="pager">
    <button
      class="pager-btn"
      :disabled="page <= 1"
      @tap="go(page - 1)"
    >
      上一页
    </button>
    <picker
      mode="selector"
      :range="pageList"
      :value="clampedPage - 1"
      @change="onPick"
    >
      <view class="pager-current">第 {{ clampedPage }} / {{ totalPages }} 页</view>
    </picker>
    <button
      class="pager-btn"
      :disabled="page >= totalPages"
      @tap="go(page + 1)"
    >
      下一页
    </button>
  </view>
</template>

<script>
export default {
  name: 'Pager',
  props: {
    // 当前页码（从 1 开始）
    page: {
      type: Number,
      default: 1
    },
    // 总页数
    totalPages: {
      type: Number,
      default: 0
    }
  },
  computed: {
    // 把当前页限制在合法范围，防止超出总页数
    clampedPage() {
      if (this.totalPages <= 0) return 1
      return Math.min(Math.max(this.page, 1), this.totalPages)
    },

    // 供 picker 选择的页码列表
    pageList() {
      const list = []
      for (let i = 1; i <= this.totalPages; i += 1) {
        list.push(String(i))
      }
      return list
    }
  },
  methods: {
    onPick(event) {
      const index = Number(event.detail.value || 0)
      this.go(index + 1)
    },

    go(target) {
      if (target < 1 || target > this.totalPages) return
      if (target === this.clampedPage) return
      this.$emit('change', target)
    }
  }
}
</script>

<style>
.pager {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12rpx;
  margin-top: 22rpx;
}

.pager-btn {
  width: 160rpx;
  height: 68rpx;
  line-height: 68rpx;
  margin: 0;
  padding: 0;
  border-radius: 8rpx;
  background: #e7eff1;
  color: #0f4c5c;
  font-size: 24rpx;
}

.pager-btn[disabled] {
  opacity: 0.5;
}

.pager-current {
  height: 68rpx;
  line-height: 68rpx;
  padding: 0 28rpx;
  border-radius: 8rpx;
  background: #0f4c5c;
  color: #fff;
  font-size: 24rpx;
  font-weight: 700;
}
</style>
