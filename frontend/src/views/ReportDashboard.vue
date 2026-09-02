<template>
  <div class="report-dashboard">
    <!-- 顶部工具栏 -->
    <div class="dash-header">
      <div class="dash-title">
        <h2>IP 资产全景看板</h2>
        <span class="dash-sub">专利 · 商标 · 奖金 · 年费 一体化数据汇报</span>
      </div>
      <div class="dash-actions">
        <el-date-picker v-model="year" type="year" placeholder="选择年份" value-format="YYYY" :clearable="false" style="width: 130px" @change="loadAll" />
        <el-popover placement="bottom-end" :width="250" trigger="click">
          <template #reference>
            <el-button type="primary">
              <el-icon class="btn-ic"><Download /></el-icon>导出
            </el-button>
          </template>
          <div class="export-opt">
            <div class="export-opt-title">选择模块</div>
            <el-checkbox-group v-model="exportModules" size="small">
              <el-checkbox v-for="m in moduleOpts" :key="m.value" :value="m.value" :label="m.label" />
            </el-checkbox-group>
            <el-divider style="margin: 8px 0" />
            <el-checkbox v-model="exportAi">
              <el-icon style="vertical-align:-2px;color:#409EFF"><MagicStick /></el-icon> 附加 AI 智能分析
            </el-checkbox>
            <div class="export-opt-tip">PPT / HTML / PDF 均按上方选项生成</div>
            <div class="export-opt-btns">
              <el-button type="success" size="small" :loading="exporting.html" @click="exportFile('html')">HTML</el-button>
              <el-button type="primary" size="small" :loading="exporting.pdf" @click="exportFile('pdf')">PDF</el-button>
              <el-button type="warning" size="small" :loading="exporting.ppt" @click="exportFile('ppt')">PPT</el-button>
            </div>
          </div>
        </el-popover>
      </div>
    </div>

    <!-- 关键指标卡 -->
    <el-row :gutter="16" class="metric-row">
      <el-col :span="4" v-for="m in metrics" :key="m.label">
        <div class="metric-card" :style="{ '--accent': m.color }">
          <div class="metric-icon"><el-icon :size="24"><component :is="m.icon" /></el-icon></div>
          <div class="metric-body">
            <div class="metric-label">{{ m.label }}</div>
            <div class="metric-value">{{ m.value }}</div>
            <div class="metric-sub">{{ m.sub }}</div>
          </div>
        </div>
      </el-col>
    </el-row>

    <!-- 图表区 -->
    <el-row :gutter="16">
      <el-col :span="12">
        <el-card shadow="never" class="chart-card">
          <template #header><span class="chart-title">专利类型分布</span></template>
          <v-chart :option="patentTypeOption" style="height: 280px" autoresize />
        </el-card>
      </el-col>
      <el-col :span="12">
        <el-card shadow="never" class="chart-card">
          <template #header><span class="chart-title">近 5 年专利申请趋势</span></template>
          <v-chart :option="patentTrendOption" style="height: 280px" autoresize />
        </el-card>
      </el-col>
    </el-row>

    <el-row :gutter="16" style="margin-top:16px">
      <el-col :span="12">
        <el-card shadow="never" class="chart-card">
          <template #header><span class="chart-title">商标状态分布</span></template>
          <v-chart :option="tmStatusOption" style="height: 280px" autoresize />
        </el-card>
      </el-col>
      <el-col :span="12">
        <el-card shadow="never" class="chart-card">
          <template #header><span class="chart-title">奖金年度发放趋势</span></template>
          <v-chart :option="bonusYearOption" style="height: 280px" autoresize />
        </el-card>
      </el-col>
    </el-row>

    <el-row :gutter="16" style="margin-top:16px">
      <el-col :span="12">
        <el-card shadow="never" class="chart-card">
          <template #header><span class="chart-title">发明人奖金 TOP10</span></template>
          <v-chart :option="inventorOption" style="height: 300px" autoresize />
        </el-card>
      </el-col>
      <el-col :span="12">
        <el-card shadow="never" class="chart-card">
          <template #header><span class="chart-title">部门奖金分布</span></template>
          <v-chart :option="deptOption" style="height: 300px" autoresize />
        </el-card>
      </el-col>
    </el-row>

    <!-- 代理机构合作统计 -->
    <el-card shadow="never" class="chart-card" style="margin-top:16px">
      <template #header><span class="chart-title">代理机构合作统计</span></template>
      <el-table :data="agencies" size="small" border stripe>
        <el-table-column prop="name" label="机构名称" min-width="200" />
        <el-table-column prop="patent_count" label="代理专利" width="100" align="center" />
        <el-table-column prop="trademark_count" label="代理商标" width="100" align="center" />
        <el-table-column label="累计费用" width="140" align="right">
          <template #default="{ row }">¥{{ formatMoney(row.total_amount) }}</template>
        </el-table-column>
      </el-table>
    </el-card>

    <div class="dash-footer">数据更新于 {{ updatedAt }}</div>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { Document, PriceTag, Money, Bell, Trophy, TrendCharts, Download, MagicStick } from '@element-plus/icons-vue'
import api from '../api'
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { BarChart, PieChart, LineChart } from 'echarts/charts'
import { TitleComponent, TooltipComponent, GridComponent, LegendComponent } from 'echarts/components'

use([CanvasRenderer, BarChart, PieChart, LineChart, TitleComponent, TooltipComponent, GridComponent, LegendComponent])

const year = ref(new Date().getFullYear().toString())
const overview = ref({})
const bonus = ref({})
const updatedAt = ref('')

const formatMoney = (n) => {
  if (!n) return '0'
  return Number(n).toLocaleString('zh-CN', { minimumFractionDigits: 0, maximumFractionDigits: 2 })
}

const metrics = computed(() => {
  const p = overview.value.patent || {}
  const t = overview.value.trademark || {}
  const f = overview.value.fee || {}
  const b = bonus.value.key_metrics || {}
  return [
    { label: '专利总数', value: p.total || 0, sub: `本年新增 ${p.new_this_year || 0}`, color: '#409EFF', icon: Document },
    { label: '商标总数', value: t.total || 0, sub: `本年新增 ${t.new_this_year || 0}`, color: '#67C23A', icon: PriceTag },
    { label: '奖金总额', value: '¥' + formatMoney(b.total_amount), sub: `本年 ¥${formatMoney(b.this_year_amount)}`, color: '#E6A23C', icon: Trophy },
    { label: '待缴年费', value: f.pending_count || 0, sub: `¥${formatMoney(f.pending_amount)}`, color: '#F56C6C', icon: Bell },
    { label: '已缴年费累计', value: '¥' + formatMoney(f.total_paid), sub: `本年 ¥${formatMoney(f.this_year_paid)}`, color: '#909399', icon: Money },
    { label: '奖金批次数', value: b.batch_count || 0, sub: `发明人 ${b.inventor_count || 0} 位`, color: '#8E44AD', icon: TrendCharts }
  ]
})

const COLORS = ['#409EFF', '#67C23A', '#E6A23C', '#F56C6C', '#8E44AD', '#00B4D8', '#FF7F50']

const patentTypeOption = computed(() => {
  const dist = overview.value.patent?.by_type || {}
  const data = Object.entries(dist).filter(([, v]) => v > 0).map(([name, value]) => ({ name, value }))
  return {
    tooltip: { trigger: 'item', formatter: '{b}: {c} 件 ({d}%)' },
    legend: { bottom: 0 },
    color: COLORS,
    series: [{
      type: 'pie',
      radius: ['42%', '68%'],
      center: ['50%', '45%'],
      avoidLabelOverlap: true,
      itemStyle: { borderRadius: 6, borderColor: '#fff', borderWidth: 2 },
      label: { formatter: '{b}\n{c} 件' },
      data
    }]
  }
})

const patentTrendOption = computed(() => {
  const trend = overview.value.patent?.trend_5yr || []
  return {
    tooltip: { trigger: 'axis' },
    grid: { left: '3%', right: '4%', bottom: '3%', top: '6%', containLabel: true },
    xAxis: { type: 'category', data: trend.map(t => t.year + '') },
    yAxis: { type: 'value', minInterval: 1 },
    series: [{
      type: 'line',
      smooth: true,
      data: trend.map(t => t.count),
      symbolSize: 8,
      itemStyle: { color: '#409EFF' },
      areaStyle: { color: 'rgba(64,158,255,0.12)' },
      label: { show: true, position: 'top' }
    }]
  }
})

const tmStatusOption = computed(() => {
  const dist = overview.value.trademark?.by_status || {}
  const data = Object.entries(dist).filter(([, v]) => v > 0).map(([name, value]) => ({ name, value }))
  return {
    tooltip: { trigger: 'item', formatter: '{b}: {c} 件 ({d}%)' },
    legend: { bottom: 0 },
    color: COLORS,
    series: [{
      type: 'pie',
      radius: '65%',
      center: ['50%', '45%'],
      itemStyle: { borderRadius: 6, borderColor: '#fff', borderWidth: 2 },
      label: { formatter: '{b}\n{c} 件' },
      data
    }]
  }
})

const bonusYearOption = computed(() => {
  const trend = bonus.value.by_year || []
  return {
    tooltip: { trigger: 'axis', formatter: (p) => `${p[0].axisValue}: ¥${formatMoney(p[0].value)}` },
    grid: { left: '3%', right: '4%', bottom: '3%', top: '6%', containLabel: true },
    xAxis: { type: 'category', data: trend.map(t => t.year + '年') },
    yAxis: { type: 'value', axisLabel: { formatter: (v) => formatMoney(v) } },
    series: [{
      type: 'bar',
      data: trend.map(t => t.total),
      itemStyle: { color: '#E6A23C', borderRadius: [4, 4, 0, 0] },
      barWidth: '45%',
      label: { show: true, position: 'top', formatter: (p) => '¥' + formatMoney(p.value) }
    }]
  }
})

const inventorOption = computed(() => {
  const list = bonus.value.top10_inventors || []
  return {
    tooltip: { trigger: 'axis', formatter: (p) => `${p[0].name}: ¥${formatMoney(p[0].value)}` },
    grid: { left: '3%', right: '10%', bottom: '3%', top: '6%', containLabel: true },
    xAxis: { type: 'value', axisLabel: { formatter: (v) => formatMoney(v) } },
    yAxis: { type: 'category', data: list.map(i => i.name).reverse() },
    series: [{
      type: 'bar',
      data: list.map(i => i.amount).reverse(),
      itemStyle: { color: '#8E44AD', borderRadius: [0, 4, 4, 0] },
      barWidth: '55%',
      label: { show: true, position: 'right', formatter: (p) => '¥' + formatMoney(p.value) }
    }]
  }
})

const deptOption = computed(() => {
  const dist = bonus.value.by_department || {}
  const sorted = Object.entries(dist).filter(([, v]) => v > 0).sort((a, b) => b[1] - a[1])
  const topN = sorted.slice(0, 8)
  const otherSum = sorted.slice(8).reduce((s, [, v]) => s + v, 0)
  const data = topN.map(([name, value]) => ({ name, value }))
  if (otherSum > 0) data.push({ name: '其他', value: otherSum })
  return {
    tooltip: { trigger: 'item', formatter: '{b}: ¥{c}' },
    legend: { bottom: 0, type: 'scroll' },
    color: COLORS,
    series: [{
      type: 'pie',
      radius: ['35%', '65%'],
      center: ['50%', '45%'],
      itemStyle: { borderRadius: 6, borderColor: '#fff', borderWidth: 2 },
      label: { formatter: '{b}\n¥{c}' },
      data
    }]
  }
})

const agencies = computed(() => overview.value.agency || [])

const loadAll = async () => {
  try {
    const [o, b] = await Promise.all([
      api.get('/reports/overview', { params: { year: year.value } }),
      api.get('/reports/bonus-stats', { params: { year: year.value } })
    ])
    overview.value = o
    bonus.value = b
    updatedAt.value = new Date().toLocaleString('zh-CN')
  } catch (e) { console.error(e) }
}

// 导出 HTML / PDF / PPT（后端生成完整文件）
const exporting = reactive({ html: false, pdf: false, ppt: false })
const moduleOpts = [
  { value: 'overview', label: '核心概览' },
  { value: 'patent', label: '专利与商标' },
  { value: 'bonus', label: '专利奖金' },
  { value: 'fee', label: '年费管理' },
  { value: 'system', label: '系统能力' }
]
const exportModules = ref(['overview', 'patent', 'bonus', 'fee', 'system'])
const exportAi = ref(false)

const exportFile = async (type) => {
  exporting[type] = true
  try {
    const token = localStorage.getItem('token')
    const params = new URLSearchParams()
    params.set('year', String(year.value))
    params.set('token', token)
    // PPT / HTML / PDF 共用同一套模块 + AI 选项
    if (exportModules.value.length && exportModules.value.length < moduleOpts.length) {
      params.set('modules', exportModules.value.join(','))
    }
    if (exportAi.value) params.set('ai', 'true')
    const res = await fetch(`/api/export/dashboard/${type}?${params.toString()}`)
    if (!res.ok) throw new Error('导出失败')
    const blob = await res.blob()
    const ext = type === 'html' ? 'html' : type
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `IP资产全景看板_${year.value}年.${ext}`
    document.body.appendChild(a)
    a.click()
    a.remove()
    URL.revokeObjectURL(url)
    ElMessage.success('导出成功，请查看下载')
  } catch (e) {
    console.error(e)
    ElMessage.error('导出失败，请稍后重试')
  } finally {
    exporting[type] = false
  }
}

onMounted(loadAll)
</script>

<style scoped>
.report-dashboard { padding: 4px; }
.dash-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}
.dash-title h2 { margin: 0; font-size: 22px; font-weight: 600; color: #303133; }
.export-opt { font-size: 13px; }
.export-opt-title { font-weight: 600; color: #606266; margin-bottom: 6px; }
.export-opt .el-checkbox-group { display: flex; flex-wrap: wrap; gap: 4px 12px; }
.export-opt-tip { font-size: 12px; color: #909399; margin: 8px 0 10px; }
.export-opt-btns { display: flex; gap: 8px; }
.export-opt-btns .el-button { flex: 1; margin-left: 0; }
.dash-sub { font-size: 13px; color: #909399; }
.dash-actions { display: flex; gap: 10px; align-items: center; }

.metric-row { margin-bottom: 4px; }
.metric-card {
  background: #fff;
  border-radius: 12px;
  padding: 18px 16px;
  display: flex;
  align-items: center;
  gap: 14px;
  box-shadow: 0 2px 10px rgba(0, 0, 0, 0.05);
  transition: transform 0.2s, box-shadow 0.2s;
  border-top: 3px solid var(--accent);
}
.metric-card:hover { transform: translateY(-3px); box-shadow: 0 6px 18px rgba(0, 0, 0, 0.1); }
.metric-icon {
  width: 46px;
  height: 46px;
  border-radius: 10px;
  background: var(--accent);
  color: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}
.metric-body { flex: 1; min-width: 0; }
.metric-label { font-size: 13px; color: #909399; }
.metric-value { font-size: 22px; font-weight: 700; color: #303133; line-height: 1.3; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.metric-sub { font-size: 12px; color: #c0c4cc; }

.chart-card { border-radius: 12px; }
.chart-title { font-weight: 600; color: #303133; }

.dash-footer { text-align: center; color: #c0c4cc; font-size: 12px; margin-top: 20px; }

@media print {
  .dash-actions { display: none; }
  .metric-card, .chart-card { box-shadow: none; }
}
</style>
