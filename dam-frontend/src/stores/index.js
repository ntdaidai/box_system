import { defineStore } from 'pinia'
import { ref } from 'vue'
import { clearResponseCache } from '@/utils/localResponseCache'

/**
 * 用户状态
 */
export const useUserStore = defineStore('user', () => {
  const token = ref(localStorage.getItem('token') || '')
  const userInfo = ref({})

  function setToken(val) {
    if (token.value !== val) {
      clearResponseCache()
    }
    token.value = val
    localStorage.setItem('token', val)
  }

  function setUserInfo(val) {
    userInfo.value = val
  }

  function logout() {
    token.value = ''
    userInfo.value = {}
    localStorage.removeItem('token')
    clearResponseCache()
  }

  return { token, userInfo, setToken, setUserInfo, logout }
})

/**
 * 告警状态
 */
export const useAlarmStore = defineStore('alarm', () => {
  const unreadCount = ref(0)

  function setUnreadCount(val) {
    unreadCount.value = val
  }

  return { unreadCount, setUnreadCount }
})
