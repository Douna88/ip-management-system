<template>
  <div class="patent-fees-page">
    <!-- Stats Summary -->
    <div class="stats-row">
      <el-card class="stat-card" shadow="hover">
        <div class="stat-content">
          <div class="stat-label">待缴年费</div>
          <div class="stat-value warning">{{ stats.pending }}</div>
        </div>
      </el-card>
      <el-card class="stat-card" shadow="hover">
        <div class="stat-content">
          <div class="stat-label">已缴年费</div>
          <div class="stat-value success">{{ stats.paid }}</div>
        </div>
      </el-card>
      <el-card class="stat-card" shadow="hover">
        <div class="stat-content">
          <div class="stat-label">逾期</div>
          <div class="stat-value danger">{{ stats.overdue }}</div>
        </div>
      </el-card>
      <el-card class="stat-card" shadow="hover">
        <div class="stat-content">
          <div class="stat-label">待缴金额合计</div>
          <div class="stat-value">¥{{ stats.pendingAmount.toFixed(0) }}</div>
        </div>
      </el-card>
    </div>

    <!-- Filters -->
    <el-card shadow="never" class="filter-card">
      <el-form :inline="true" :model="filters" @submit.prevent>
        <el-form-item>
          <el-input v-model="filters.search" placeholder="搜索专利名称/申请号" clearable style="width: 220px" @clear="loadData" @keyup.enter="loadData" />
        </el-form-item>
        <el-form-item>
          <el-select v-model="filters.status" placeholder="缴费状态" clearable style="width: 130px" @change="loadData">
            <el-option label="待缴" value="待缴" />
            <el-option label="已缴" value="已缴" />
            <el-option label="逾期" value="逾期" />
            <el-option label="滞纳金" value="滞纳金" />
          </el-select>
        </el-form-item>
        <el-form-item>
          <el-select v-model="filters.urgency" placeholder="紧急度" clearable style="width: 130px" @change="loadData">
            <el-option label="已逾期" value="overdue" />
            <el-option label="7天内" value="urgent" />
            <el-option label="30天内" value="warning" />
            <el-option label="90天内" value="notice" />
          </el-select>
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="loadData">查询</el-button>
          <el-button @click="resetFilters">重置</el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <!-- 提示横幅：年费自动计算/批量导入开发中 -->
    <el-alert class="tip-alert" type="info" :closable="false" show-icon>
      <template #title>
        <span>本页字段已对齐「专利清单」Excel 格式。新增/导入专利时，系统会根据年费阶梯规则自动算出应缴金额，无需手动录入。</span>
      </template>
    </el-alert>

    <!-- Table -->
    <el-card shadow="never">
      <el-table :data="tableData" v-loading="loading" border stripe style="width: 100%">
        <el-table-column label="专利名称" min-width="200" show-overflow-tooltip>
          <template #default="{ row }">
            <el-link type="primary" @click="goToPatent(row.patent_id)">{{ row.patent_name }}</el-link>
          </template>
        </el-table-column>
        <el-table-column prop="application_no" label="申请号" width="140" />
        <el-table-column prop="patent_type" label="申请类型" width="100" align="center" />
        <el-table-column prop="fee_year" label="年度" width="70" align="center">
          <template #default="{ row }">第{{ row.fee_year }}年</template>
        </el-table-column>
        <el-table-column label="应缴日期" width="110" align="center">
          <template #default="{ row }">
            <span :class="{ 'text-danger': row.urgency === 'overdue', 'text-warning': row.urgency === 'urgent' }">
              {{ row.due_date || '-' }}
            </span>
          </template>
        </el-table-column>
        <el-table-column label="剩余天数" width="90" align="center">
          <template #default="{ row }">
            <el-tag v-if="row.days_left !== null" :type="urgencyTagType(row.urgency)" size="small" effect="dark">
              {{ row.days_left < 0 ? `逾期${-row.days_left}天` : `${row.days_left}天` }}
            </el-tag>
            <span v-else>-</span>
          </template>
        </el-table-column>
        <el-table-column label="应缴金额" width="100" align="right">
          <template #default="{ row }">¥{{ row.standard_amount || 0 }}</template>
        </el-table-column>
        <el-table-column label="实缴金额" width="100" align="right">
          <template #default="{ row }">{{ row.actual_pay_amount ? `¥${row.actual_pay_amount}` : '-' }}</template>
        </el-table-column>
        <el-table-column label="状态" width="80" align="center">
          <template #default="{ row }">
            <el-tag :type="statusTagType(row.status)" size="small">{{ row.status }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="缴费日期" width="110" align="center">
          <template #default="{ row }">{{ row.actual_pay_date || '-' }}</template>
        </el-table-column>
        <el-table-column label="凭证" width="80" align="center">
          <template #default="{ row }">
            <el-button v-if="row.receipt_file_id" text type="primary" size="small" @click="viewFeeFile(row.receipt_file_id)">查看</el-button>
            <span v-else>-</span>
          </template>
        </el-table-column>
        <el-table-column label="备注" min-width="160" show-overflow-tooltip>
          <template #default="{ row }">
            <span class="notes-cell">{{ row.notes || '-' }}</span>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="180" align="center" fixed="right">
          <template #default="{ row }">
            <div class="action-btns">
              <el-tooltip v-if="row.status !== '已缴'" content="标记缴费" placement="top">
                <el-button circle size="small" type="primary" plain @click="openPayDialog(row)">
                  <el-icon><Money /></el-icon>
                </el-button>
              </el-tooltip>
              <el-tooltip v-if="row.status === '已缴' && !row.receipt_file_id" content="上传凭证" placement="top">
                <el-button circle size="small" type="success" plain @click="uploadReceipt(row)">
                  <el-icon><Upload /></el-icon>
                </el-button>
              </el-tooltip>
              <el-tooltip content="编辑备注" placement="top">
                <el-button circle size="small" type="warning" plain @click="openNotesDialog(row)">
                  <el-icon><EditPen /></el-icon>
                </el-button>
              </el-tooltip>
              <el-tooltip content="删除记录" placement="top">
                <el-button circle size="small" type="danger" plain @click="confirmDelete(row)">
                  <el-icon><Delete /></el-icon>
                </el-button>
              </el-tooltip>
            </div>
          </template>
        </el-table-column>
      </el-table>

      <el-pagination
        class="pagination"
        v-model:current-page="filters.page"
        v-model:page-size="filters.page_size"
        :total="total"
        :page-sizes="[20, 50, 100]"
        layout="total, sizes, prev, pager, next"
        @size-change="loadData"
        @current-change="loadData"
      />
    </el-card>

    <!-- Pay Dialog -->
    <el-dialog v-model="payDialogVisible" title="标记缴费" width="450px">
      <el-form :model="payForm" label-width="100px">
        <el-form-item label="专利名称">
          <span>{{ payForm.patent_name }}</span>
        </el-form-item>
        <el-form-item label="年费年度">
          <span>第{{ payForm.fee_year }}年</span>
        </el-form-item>
        <el-form-item label="应缴金额">
          <span>¥{{ payForm.standard_amount || 0 }}</span>
        </el-form-item>
        <el-form-item label="实缴金额">
          <el-input-number v-model="payForm.pay_amount" :min="0" :precision="2" style="width: 200px" />
        </el-form-item>
        <el-form-item label="缴费日期">
          <el-date-picker v-model="payForm.pay_date" type="date" value-format="YYYY-MM-DD" placeholder="选择日期" style="width: 200px" />
        </el-form-item>
        <el-form-item label="收据编号">
          <el-input v-model="payForm.receipt_no" placeholder="可选" style="width: 200px" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="payDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="confirmPay">确认缴费</el-button>
      </template>
    </el-dialog>

    <!-- 备注编辑对话框 -->
    <el-dialog v-model="notesDialogVisible" title="编辑备注" width="450px">
      <el-form :model="notesForm" label-width="100px">
        <el-form-item label="专利">
          <span>{{ notesForm.patent_name }} · 第{{ notesForm.fee_year }}年</span>
        </el-form-item>
        <el-form-item label="备注">
          <el-input
            v-model="notesForm.notes"
            type="textarea"
            :rows="3"
            placeholder="例如：已缴滞纳金 5 元；通过 XX 代理；申请费减 85%"
            maxlength="200"
            show-word-limit
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="notesDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="confirmNotes">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Money, Upload, EditPen, Delete } from '@element-plus/icons-vue'
import api from '../../api'

const router = useRouter()

const loading = ref(false)
const tableData = ref([])
const total = ref(0)
const stats = reactive({ pending: 0, paid: 0, overdue: 0, pendingAmount: 0 })

const filters = reactive({
  search: '',
  status: '',
  urgency: '',
  page: 1,
  page_size: 20
})

const payDialogVisible = ref(false)
const payForm = reactive({
  id: null,
  patent_name: '',
  fee_year: 1,
  standard_amount: 0,
  pay_amount: 0,
  pay_date: '',
  receipt_no: ''
})

// 备注编辑
const notesDialogVisible = ref(false)
const notesForm = reactive({
  id: null,
  patent_name: '',
  fee_year: 1,
  notes: ''
})

const urgencyTagType = (urgency) => {
  const map = { overdue: 'danger', urgent: 'danger', warning: 'warning', notice: 'info', normal: '', paid: 'success' }
  return map[urgency] || ''
}

const statusTagType = (status) => {
  const map = { '已缴': 'success', '待缴': 'warning', '逾期': 'danger', '滞纳金': 'danger' }
  return map[status] || ''
}

const loadData = async () => {
  loading.value = true
  try {
    const params = { page: filters.page, page_size: filters.page_size }
    if (filters.search) params.search = filters.search
    if (filters.status) params.status = filters.status
    if (filters.urgency) params.urgency = filters.urgency

    const res = await api.get('/fees/patent-fees', { params })
    tableData.value = res.items
    total.value = res.total

    // Calculate stats
    stats.pending = res.items.filter(i => i.status === '待缴').length
    stats.paid = res.items.filter(i => i.status === '已缴').length
    stats.overdue = res.items.filter(i => i.urgency === 'overdue').length
    stats.pendingAmount = res.items.filter(i => i.status === '待缴').reduce((s, i) => s + (i.standard_amount || 0), 0)
  } catch (e) {
    // error handled by interceptor
  } finally {
    loading.value = false
  }
}

const resetFilters = () => {
  filters.search = ''
  filters.status = ''
  filters.urgency = ''
  filters.page = 1
  loadData()
}

const goToPatent = (id) => {
  router.push(`/patent/${id}`)
}

const openPayDialog = (row) => {
  payForm.id = row.id
  payForm.patent_name = row.patent_name
  payForm.fee_year = row.fee_year
  payForm.standard_amount = row.standard_amount
  payForm.pay_amount = row.standard_amount || 0
  payForm.pay_date = new Date().toISOString().slice(0, 10)
  payForm.receipt_no = ''
  payDialogVisible.value = true
}

const confirmPay = async () => {
  try {
    const params = new URLSearchParams()
    if (payForm.pay_date) params.append('pay_date', payForm.pay_date)
    if (payForm.pay_amount > 0) params.append('pay_amount', payForm.pay_amount)
    if (payForm.receipt_no) params.append('receipt_no', payForm.receipt_no)

    await api.put(`/fees/patent-fees/${payForm.id}/pay?${params.toString()}`)
    ElMessage.success('缴费标记成功')
    payDialogVisible.value = false
    loadData()
  } catch (e) {
    // error handled by interceptor
  }
}

// View fee receipt file
const viewFeeFile = (fileId) => {
  window.open(`/api/files/${fileId}/download?token=${localStorage.getItem('token')}`, '_blank')
}

// 打开/保存备注
const openNotesDialog = (row) => {
  notesForm.id = row.id
  notesForm.patent_name = row.patent_name
  notesForm.fee_year = row.fee_year
  notesForm.notes = row.notes || ''
  notesDialogVisible.value = true
}
const confirmNotes = async () => {
  try {
    await api.put(`/fees/patent-fees/${notesForm.id}/notes`, { notes: notesForm.notes })
    ElMessage.success('备注已保存')
    notesDialogVisible.value = false
    loadData()
  } catch (e) {
    // handled by interceptor
  }
}

// 删除年费记录（二次确认）
const confirmDelete = (row) => {
  ElMessageBox.confirm(
    `确定要删除「${row.patent_name}」第${row.fee_year}年的年费记录吗？此操作不可撤销。`,
    '删除确认',
    { type: 'warning', confirmButtonText: '删除', cancelButtonText: '取消', confirmButtonClass: 'el-button--danger' }
  ).then(async () => {
    try {
      await api.delete(`/fees/patent-fees/${row.id}`)
      ElMessage.success('已删除')
      loadData()
    } catch (e) {
      // handled by interceptor
    }
  }).catch(() => {})
}
const uploadReceipt = (row) => {
  const input = document.createElement('input')
  input.type = 'file'
  input.accept = '.doc,.docx,.xls,.xlsx,.pdf'
  input.onchange = async (e) => {
    const file = e.target.files[0]
    if (!file) return
    const formData = new FormData()
    formData.append('file', file)
    try {
      const res = await fetch(`/api/files/upload?business_type=patent_fee&business_id=${row.id}`, {
        method: 'POST',
        headers: { 'Authorization': `Bearer ${localStorage.getItem('token')}` },
        body: formData
      })
      if (res.ok) {
        const data = await res.json()
        if (data.id) {
          await api.put(`/patents/${row.patent_id}/fees/${row.id}`, {
            ...row,
            receipt_file_id: data.id
          })
          ElMessage.success('凭证上传成功')
          loadData()
        }
      } else {
        ElMessage.error('上传失败')
      }
    } catch (err) {
      ElMessage.error('上传失败: ' + err.message)
    }
  }
  input.click()
}

onMounted(() => {
  loadData()
})
</script>

<style scoped>
.stats-row { display: flex; gap: 16px; margin-bottom: 16px; }
.stat-card { flex: 1; }
.stat-content { text-align: center; }
.stat-label { font-size: 13px; color: #909399; margin-bottom: 8px; }
.stat-value { font-size: 28px; font-weight: bold; color: #303133; }
.stat-value.warning { color: #e6a23c; }
.stat-value.success { color: #67c23a; }
.stat-value.danger { color: #f56c6c; }
.filter-card { margin-bottom: 16px; }
.pagination { margin-top: 16px; justify-content: flex-end; }
.text-danger { color: #f56c6c; font-weight: bold; }
.text-warning { color: #e6a23c; font-weight: bold; }
.action-btns { display: flex; gap: 6px; justify-content: center; }
.notes-cell { color: #606266; font-size: 12.5px; }
.tip-alert { margin-bottom: 16px; border-radius: 8px; }
</style>
