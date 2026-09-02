<template>
  <div>
    <!-- Stats Cards -->
    <el-row :gutter="16" class="stats-row">
      <el-col :span="6">
        <el-card shadow="hover">
          <div class="stat-card">
            <div class="stat-icon" style="background:#409EFF"><el-icon size="28"><Document /></el-icon></div>
            <div class="stat-info">
              <div class="stat-label">专利总数</div>
              <div class="stat-value">{{ stats.patent_total || 0 }}</div>
              <div class="stat-sub">已授权 {{ stats.patent_active || 0 }}</div>
            </div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover">
          <div class="stat-card">
            <div class="stat-icon" style="background:#67C23A"><el-icon size="28"><PriceTag /></el-icon></div>
            <div class="stat-info">
              <div class="stat-label">商标总数</div>
              <div class="stat-value">{{ stats.trademark_total || 0 }}</div>
              <div class="stat-sub">有效 {{ stats.trademark_active || 0 }}</div>
            </div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover">
          <div class="stat-card">
            <div class="stat-icon" style="background:#E6A23C"><el-icon size="28"><Money /></el-icon></div>
            <div class="stat-info">
              <div class="stat-label">待缴年费</div>
              <div class="stat-value">{{ stats.fee_pending_count || 0 }}</div>
              <div class="stat-sub">¥{{ formatNum(stats.fee_pending_amount) }}</div>
            </div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover">
          <div class="stat-card">
            <div class="stat-icon" style="background:#F56C6C"><el-icon size="28"><Bell /></el-icon></div>
            <div class="stat-info">
              <div class="stat-label">商标续展提醒</div>
              <div class="stat-value">{{ stats.tm_renewal_count || 0 }}</div>
              <div class="stat-sub">12个月内到期</div>
            </div>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <!-- Patent Type Distribution + Reminders -->
    <el-row :gutter="16" style="margin-top:16px">
      <el-col :span="12">
        <el-card shadow="hover">
          <template #header><span>专利类型分布</span></template>
          <v-chart v-if="typeChartData.length" :option="typeChartOption" style="height: 260px" autoresize />
          <el-empty v-else description="暂无数据" :image-size="60" />
        </el-card>
      </el-col>
      <el-col :span="12">
        <el-card shadow="hover">
          <template #header>
            <div style="display:flex;justify-content:space-between;align-items:center">
              <span>到期提醒</span>
              <el-button text @click="$router.push('/reminders')">查看全部</el-button>
            </div>
          </template>
          <div v-for="r in reminders.fee_reminders?.slice(0, 5)" :key="r.id" class="reminder-item" :class="r.urgency">
            <div class="reminder-main">
              <span class="reminder-tag" :class="r.urgency">{{ urgencyLabel(r.urgency) }}</span>
              <span class="reminder-name">{{ r.patent_name }}</span>
            </div>
            <div class="reminder-meta">
              第{{ r.fee_year }}年 · {{ r.due_date }} · 剩余{{ r.days_left }}天
            </div>
          </div>
          <div v-for="r in reminders.tm_reminders?.slice(0, 3)" :key="'tm'+r.id" class="reminder-item" :class="r.urgency">
            <div class="reminder-main">
              <span class="reminder-tag" :class="r.urgency">{{ urgencyLabel(r.urgency) }}</span>
              <span class="reminder-name">™ {{ r.trademark_name }}</span>
            </div>
            <div class="reminder-meta">
              到期: {{ r.valid_until }} · 剩余{{ r.days_left }}天
            </div>
          </div>
          <el-empty v-if="(!reminders.fee_reminders || reminders.fee_reminders.length === 0) && (!reminders.tm_reminders || reminders.tm_reminders.length === 0)" description="暂无到期提醒" :image-size="60" />
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup>
import { ref, onMounted, computed } from 'vue'
import { Document, PriceTag, Money, Bell } from '@element-plus/icons-vue'
import api from '../api'
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { BarChart } from 'echarts/charts'
import { TitleComponent, TooltipComponent, GridComponent, LegendComponent } from 'echarts/components'

use([CanvasRenderer, BarChart, TitleComponent, TooltipComponent, GridComponent, LegendComponent])

const stats = ref({})
const reminders = ref({})

const formatNum = (n) => {
  if (!n) return '0'
  return Number(n).toLocaleString('zh-CN', { minimumFractionDigits: 0, maximumFractionDigits: 2 })
}

const urgencyLabel = (u) => ({ overdue: '已逾期', urgent: '紧急', warning: '注意', notice: '提前' }[u] || u)

const getTypeColor = (type) => {
  const colors = { '发明': '#409EFF', '实用新型': '#67C23A', '外观': '#E6A23C', '软著': '#909399', '软产': '#F56C6C', '未分类': '#C0C4CC' }
  return colors[type] || '#409EFF'
}

const typeChartData = computed(() => {
  const dist = stats.value.patent_type_dist || {}
  return Object.entries(dist).map(([name, value]) => ({ name, value })).sort((a, b) => a.value - b.value)
})

const typeChartOption = computed(() => {
  const data = typeChartData.value
  return {
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'shadow' },
      formatter: (params) => `${params[0].name}: <strong>${params[0].value} 件</strong>`
    },
    grid: { left: '3%', right: '12%', bottom: '3%', top: '5%', containLabel: true },
    xAxis: { type: 'value', minInterval: 1, axisLabel: { formatter: '{value} 件' } },
    yAxis: { type: 'category', data: data.map(d => d.name), axisLabel: { width: 80, overflow: 'truncate' } },
    series: [{
      type: 'bar',
      data: data.map(d => ({
        value: d.value,
        itemStyle: { color: getTypeColor(d.name), borderRadius: [0, 4, 4, 0] }
      })),
      barWidth: '55%',
      label: { show: true, position: 'right', formatter: '{c} 件' }
    }]
  }
})

onMounted(async () => {
  try {
    const [s, r] = await Promise.all([
      api.get('/dashboard/stats'),
      api.get('/dashboard/reminders?days=90')
    ])
    stats.value = s
    reminders.value = r
  } catch (e) { console.error(e) }
})
</script>

<style scoped>
.stats-row .el-card { border-radius: 8px; }
.stat-card { display: flex; align-items: center; gap: 16px; }
.stat-icon { width: 56px; height: 56px; border-radius: 8px; display: flex; align-items: center; justify-content: center; color: #fff; }
.stat-info { flex: 1; }
.stat-label { font-size: 14px; color: #909399; }
.stat-value { font-size: 28px; font-weight: bold; color: #303133; line-height: 1.4; }
.stat-sub { font-size: 12px; color: #c0c4cc; }
.reminder-item { padding: 10px 0; border-bottom: 1px solid #f0f0f0; }
.reminder-item:last-child { border-bottom: none; }
.reminder-main { display: flex; align-items: center; gap: 8px; margin-bottom: 4px; }
.reminder-tag { font-size: 12px; padding: 2px 8px; border-radius: 4px; color: #fff; }
.reminder-tag.overdue { background: #F56C6C; }
.reminder-tag.urgent { background: #E6A23C; }
.reminder-tag.warning { background: #409EFF; }
.reminder-tag.notice { background: #67C23A; }
.reminder-name { font-weight: 500; color: #303133; }
.reminder-meta { font-size: 12px; color: #909399; margin-left: 52px; }
</style>
