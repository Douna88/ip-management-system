<template>
  <div>
    <el-card shadow="never">
      <template #header><span>待办与提醒</span></template>
      <el-tabs v-model="activeTab">
        <el-tab-pane :label="`专利年费 (${feeReminders.length})`" name="fees">
          <el-table :data="feeReminders" border stripe v-loading="loading">
            <el-table-column label="紧急程度" width="100"><template #default="{row}"><el-tag :type="urgencyType(row.urgency)" size="small">{{ urgencyLabel(row.urgency) }}</el-tag></template></el-table-column>
            <el-table-column prop="patent_name" label="专利名称" min-width="200"><template #default="{row}"><el-link type="primary" @click="$router.push(`/patent/${row.patent_id}`)">{{ row.patent_name }}</el-link></template></el-table-column>
            <el-table-column prop="patent_type" label="类型" width="90" />
            <el-table-column prop="application_no" label="申请号" width="150" />
            <el-table-column prop="fee_year" label="年度" width="70" />
            <el-table-column prop="due_date" label="应缴日" width="110" />
            <el-table-column label="剩余天数" width="90"><template #default="{row}"><span :style="row.days_left < 0 ? 'color:#F56C6C;font-weight:bold' : row.days_left <= 30 ? 'color:#E6A23C' : ''">{{ row.days_left < 0 ? '已逾期' + Math.abs(row.days_left) + '天' : row.days_left + '天' }}</span></template></el-table-column>
            <el-table-column label="标准金额" width="100"><template #default="{row}">¥{{ row.standard_amount || 0 }}</template></el-table-column>
            <el-table-column label="费减金额" width="100"><template #default="{row}">¥{{ row.reduced_amount || 0 }}</template></el-table-column>
          </el-table>
        </el-tab-pane>
        <el-tab-pane :label="`商标续展 (${tmReminders.length})`" name="tm">
          <el-table :data="tmReminders" border stripe>
            <el-table-column label="紧急程度" width="100"><template #default="{row}"><el-tag :type="urgencyType(row.urgency)" size="small">{{ urgencyLabel(row.urgency) }}</el-tag></template></el-table-column>
            <el-table-column prop="trademark_name" label="商标名称" min-width="200"><template #default="{row}"><el-link type="primary" @click="$router.push(`/trademark/${row.id}`)">{{ row.trademark_name }}</el-link></template></el-table-column>
            <el-table-column prop="trademark_no" label="注册号" width="120" />
            <el-table-column prop="scope_group" label="范围" width="100" />
            <el-table-column prop="valid_until" label="有效期至" width="110" />
            <el-table-column label="剩余天数" width="90"><template #default="{row}"><span :style="row.days_left < 0 ? 'color:#F56C6C;font-weight:bold' : row.days_left <= 30 ? 'color:#E6A23C' : ''">{{ row.days_left < 0 ? '已逾期' + Math.abs(row.days_left) + '天' : row.days_left + '天' }}</span></template></el-table-column>
          </el-table>
        </el-tab-pane>
      </el-tabs>
    </el-card>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import api from '../api'

const loading = ref(false)
const activeTab = ref('fees')
const feeReminders = ref([])
const tmReminders = ref([])

const urgencyLabel = (u) => ({ overdue: '已逾期', urgent: '紧急', warning: '注意', notice: '提前' }[u] || u)
const urgencyType = (u) => ({ overdue: 'danger', urgent: 'warning', warning: '', notice: 'info' }[u] || '')

onMounted(async () => {
  loading.value = true
  try {
    const res = await api.get('/dashboard/reminders?days=365')
    feeReminders.value = res.fee_reminders || []
    tmReminders.value = res.tm_reminders || []
  } catch (e) {} finally { loading.value = false }
})
</script>
