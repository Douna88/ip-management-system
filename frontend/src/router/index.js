import { createRouter, createWebHistory } from 'vue-router'

const routes = [
  { path: '/login', name: 'Login', component: () => import('../views/Login.vue') },
  {
    path: '/',
    component: () => import('../layout/MainLayout.vue'),
    redirect: '/dashboard',
    children: [
      { path: 'dashboard', name: 'Dashboard', component: () => import('../views/Dashboard.vue'), meta: { title: '工作台' } },
      { path: 'reminders', name: 'Reminders', component: () => import('../views/Reminders.vue'), meta: { title: '待办与提醒' } },
      { path: 'patent', name: 'PatentList', component: () => import('../views/patent/PatentList.vue'), meta: { title: '专利列表' } },
      { path: 'patent/:id', name: 'PatentDetail', component: () => import('../views/patent/PatentDetail.vue'), meta: { title: '专利详情' } },
      { path: 'patent-fees', name: 'PatentFees', component: () => import('../views/patent/PatentFees.vue'), meta: { title: '专利年费' } },
      { path: 'patent-bonus', name: 'PatentBonus', component: () => import('../views/patent/PatentBonus.vue'), meta: { title: '专利奖金' } },
      { path: 'trademark', name: 'TrademarkList', component: () => import('../views/trademark/TrademarkList.vue'), meta: { title: '商标列表' } },
      { path: 'trademark/:id', name: 'TrademarkDetail', component: () => import('../views/trademark/TrademarkDetail.vue'), meta: { title: '商标详情' } },
      { path: 'trademark-scope', name: 'TrademarkScope', component: () => import('../views/trademark/TrademarkScope.vue'), meta: { title: '注册范围库' } },
      { path: 'agency', name: 'AgencyList', component: () => import('../views/agency/AgencyList.vue'), meta: { title: '代理机构' } },
      { path: 'agency/:id', name: 'AgencyDetail', component: () => import('../views/agency/AgencyDetail.vue'), meta: { title: '代理机构详情' } },
      { path: 'file-center', name: 'FileCenter', component: () => import('../views/FileCenter.vue'), meta: { title: '文件中心' } },
      { path: 'reports', name: 'Reports', component: () => import('../views/Reports.vue'), meta: { title: '导入导出中心' } },
      { path: 'report-dashboard', name: 'ReportDashboard', component: () => import('../views/ReportDashboard.vue'), meta: { title: '数据看板' } },
      { path: 'settings', name: 'Settings', component: () => import('../views/Settings.vue'), meta: { title: '系统设置' } },
    ]
  }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

router.beforeEach((to, from, next) => {
  const token = localStorage.getItem('token')
  if (to.path !== '/login' && !token) {
    next('/login')
  } else if (to.path === '/login' && token) {
    next('/')
  } else {
    next()
  }
})

export default router
