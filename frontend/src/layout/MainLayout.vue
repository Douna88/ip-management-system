<template>
  <el-container class="layout-container">
    <!-- Sidebar -->
    <el-aside :width="isCollapse ? '64px' : '220px'" class="sidebar">
      <div class="logo">
        <span v-if="!isCollapse">IP管理系统</span>
        <span v-else>IP</span>
      </div>
      <el-menu
        :default-active="activeMenu"
        :collapse="isCollapse"
        :router="true"
        background-color="#304156"
        text-color="#bfcbd9"
        active-text-color="#409EFF"
        class="sidebar-menu"
      >
        <el-menu-item index="/dashboard">
          <el-icon><DataBoard /></el-icon>
          <span>工作台</span>
        </el-menu-item>

        <el-menu-item index="/reminders">
          <el-icon><Bell /></el-icon>
          <span>待办与提醒</span>
        </el-menu-item>

        <el-sub-menu index="patent">
          <template #title>
            <el-icon><Document /></el-icon>
            <span>专利</span>
          </template>
          <el-menu-item index="/patent">专利列表</el-menu-item>
          <el-menu-item index="/patent-fees">专利年费</el-menu-item>
          <el-menu-item index="/patent-bonus">专利奖金</el-menu-item>
          <el-menu-item index="/agency">代理机构</el-menu-item>
        </el-sub-menu>

        <el-sub-menu index="trademark">
          <template #title>
            <el-icon><PriceTag /></el-icon>
            <span>商标</span>
          </template>
          <el-menu-item index="/trademark">商标列表</el-menu-item>
          <el-menu-item index="/trademark-scope">注册范围库</el-menu-item>
        </el-sub-menu>

        <el-menu-item index="/file-center">
          <el-icon><FolderOpened /></el-icon>
          <span>文件中心</span>
        </el-menu-item>

        <el-menu-item index="/reports">
          <el-icon><TrendCharts /></el-icon>
          <span>报表与导出</span>
        </el-menu-item>

        <el-menu-item index="/report-dashboard">
          <el-icon><DataAnalysis /></el-icon>
          <span>数据看板</span>
        </el-menu-item>

        <el-menu-item index="/settings">
          <el-icon><Setting /></el-icon>
          <span>系统设置</span>
        </el-menu-item>
      </el-menu>
    </el-aside>

    <!-- Main content -->
    <el-container>
      <el-header class="header">
        <div class="header-left">
          <el-icon class="collapse-btn" @click="isCollapse = !isCollapse">
            <Fold v-if="!isCollapse" />
            <Expand v-else />
          </el-icon>
          <span class="page-title">{{ currentTitle }}</span>
        </div>
        <div class="header-right">
          <el-dropdown>
            <span class="user-info">
              <el-icon><User /></el-icon>
              {{ user?.display_name || '用户' }}
            </span>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item @click="handleLogout">退出登录</el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
        </div>
      </el-header>

      <el-main class="main-content">
        <router-view />
      </el-main>
    </el-container>

    <AiAssistant />
  </el-container>
</template>

<script setup>
import { ref, computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { DataBoard, Bell, Document, PriceTag, Setting, Fold, Expand, User, FolderOpened, TrendCharts, DataAnalysis } from '@element-plus/icons-vue'
import AiAssistant from '../components/AiAssistant.vue'

const route = useRoute()
const router = useRouter()
const isCollapse = ref(false)

const user = computed(() => {
  try { return JSON.parse(localStorage.getItem('user') || 'null') } catch { return null }
})

const activeMenu = computed(() => {
  const path = route.path
  if (path.startsWith('/patent/')) return '/patent'
  if (path.startsWith('/trademark/')) return '/trademark'
  return path
})

const currentTitle = computed(() => route.meta?.title || '工作台')

const handleLogout = () => {
  localStorage.removeItem('token')
  localStorage.removeItem('user')
  router.push('/login')
}
</script>

<style scoped>
.layout-container { height: 100vh; }
.sidebar { background-color: #304156; transition: width 0.3s; overflow: hidden; }
.logo { height: 60px; display: flex; align-items: center; justify-content: center; color: #fff; font-size: 18px; font-weight: bold; border-bottom: 1px solid #3a4a5c; }
.sidebar-menu { border-right: none; }
.header { background: #fff; border-bottom: 1px solid #e6e6e6; display: flex; align-items: center; justify-content: space-between; padding: 0 20px; }
.header-left { display: flex; align-items: center; gap: 16px; }
.collapse-btn { cursor: pointer; font-size: 20px; }
.page-title { font-size: 16px; font-weight: 500; }
.user-info { display: flex; align-items: center; gap: 6px; cursor: pointer; color: #333; }
.main-content { background: #f0f2f5; padding: 20px; overflow-y: auto; }
</style>
