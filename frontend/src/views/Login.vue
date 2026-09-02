<template>
  <div class="login-container">
    <div class="login-card">
      <h1 class="login-title">IP管理系统</h1>
      <p class="login-subtitle">专利 · 商标 · 代理机构 · 奖金管理</p>
      <el-form :model="form" @submit.prevent="handleLogin" class="login-form">
        <el-form-item>
          <el-input v-model="form.username" placeholder="用户名" prefix-icon="User" size="large" />
        </el-form-item>
        <el-form-item>
          <el-input v-model="form.password" type="password" placeholder="密码" prefix-icon="Lock" size="large" show-password @keyup.enter="handleLogin" />
        </el-form-item>
        <el-button type="primary" size="large" style="width:100%" :loading="loading" @click="handleLogin">登录</el-button>
      </el-form>
      <p class="login-hint">默认账号: admin / admin123</p>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import api from '../api'

const router = useRouter()
const loading = ref(false)
const form = ref({ username: 'admin', password: 'admin123' })

const handleLogin = async () => {
  if (!form.value.username || !form.value.password) {
    ElMessage.warning('请输入用户名和密码')
    return
  }
  loading.value = true
  try {
    const res = await api.post('/auth/login', form.value)
    localStorage.setItem('token', res.access_token)
    localStorage.setItem('user', JSON.stringify(res.user))
    ElMessage.success('登录成功')
    router.push('/')
  } catch (e) {
    // error handled by interceptor
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.login-container { height: 100vh; display: flex; align-items: center; justify-content: center; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); }
.login-card { background: #fff; padding: 40px; border-radius: 8px; box-shadow: 0 8px 32px rgba(0,0,0,0.1); width: 400px; text-align: center; }
.login-title { font-size: 28px; color: #303133; margin-bottom: 8px; }
.login-subtitle { color: #909399; font-size: 14px; margin-bottom: 30px; }
.login-form { text-align: left; }
.login-hint { margin-top: 20px; color: #c0c4cc; font-size: 12px; }
</style>
