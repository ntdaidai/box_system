/**
 * 文档管理路由配置
 */

export default [
  {
    path: '/document',
    name: 'DocumentManagement',
    component: () => import('@/views/DocumentManagement.vue'),
    meta: {
      title: '文档管理',
      icon: 'Document',
      requireAuth: true
    }
  },
  {
    path: '/document/editor/:documentId',
    name: 'DocumentEditor',
    component: () => import('@/views/DocumentEditor.vue'),
    meta: {
      title: '文档编辑',
      icon: 'Edit',
      requireAuth: true,
      hidden: true // 不在菜单中显示
    }
  }
]
