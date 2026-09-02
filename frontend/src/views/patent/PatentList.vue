<template>
  <div>
    <!-- Search & Filter Bar -->
    <el-card shadow="never" class="filter-bar">
      <div class="filter-row">
        <div class="filter-left">
          <el-input v-model="filters.search" placeholder="搜索专利名称/申请号/发明人/项目" prefix-icon="Search" clearable style="width: 220px" @clear="loadData" @keyup.enter="loadData" />
          <el-select v-model="filters.patent_type" placeholder="专利类型" clearable style="width: 120px" @change="loadData">
            <el-option v-for="t in patentTypes" :key="t" :label="t" :value="t" />
          </el-select>
          <el-select v-model="filters.status" placeholder="状态" clearable style="width: 120px" @change="loadData">
            <el-option v-for="s in patentStatuses" :key="s" :label="s" :value="s" />
          </el-select>
          <el-select v-model="filters.apply_year" placeholder="申请年度" clearable style="width: 110px" @change="loadData">
            <el-option v-for="y in yearOptions" :key="'a' + y" :label="y + ' 年'" :value="String(y)" />
          </el-select>
          <el-select v-model="filters.grant_year" placeholder="授权年度" clearable style="width: 110px" @change="loadData">
            <el-option v-for="y in yearOptions" :key="'g' + y" :label="y + ' 年'" :value="String(y)" />
          </el-select>
        </div>
        <div class="filter-right">
          <el-button type="primary" :icon="Search" @click="loadData">查询</el-button>
          <el-button type="success" :icon="Plus" @click="openCreate">新增</el-button>
          <el-button type="warning" plain :icon="Upload" :loading="importing" @click="triggerImport">导入Excel</el-button>
        </div>
      </div>
      <input ref="importInput" type="file" accept=".xlsx,.xls" style="display:none" @change="handleImportFile" />
    </el-card>

    <!-- Patent Table -->
    <el-card shadow="never" style="margin-top:12px">
      <el-table :data="tableData" v-loading="loading" border stripe style="width:100%" @row-dblclick="rowDblClick">
        <el-table-column prop="application_no" label="申请号" width="150" fixed="left" />
        <el-table-column prop="patent_name" label="专利名称" min-width="200" show-overflow-tooltip>
          <template #default="{ row }">
            <el-link type="primary" @click="goDetail(row.id)">{{ row.patent_name }}</el-link>
          </template>
        </el-table-column>
        <el-table-column prop="patent_type" label="类型" width="90">
          <template #default="{ row }">
            <el-tag :type="typeTagType(row.patent_type)" size="small">{{ row.patent_type }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="status" label="状态" width="90">
          <template #default="{ row }">
            <el-tag :type="statusTagType(row.status)" size="small">{{ row.status }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="application_date" label="申请日" width="110" />
        <el-table-column prop="authorization_no" label="授权号" width="140" show-overflow-tooltip />
        <el-table-column prop="authorization_date" label="授权日" width="110" />
        <el-table-column prop="inventors" label="发明人" width="120" show-overflow-tooltip />
        <el-table-column prop="applicant" label="权利人" width="120" show-overflow-tooltip />
        <el-table-column prop="correspondence_project" label="对应项目" width="140" show-overflow-tooltip />
        <el-table-column prop="correspondence_product" label="对应产品" width="120" show-overflow-tooltip />
        <el-table-column label="快速预审" width="80" align="center">
          <template #default="{ row }">
            <el-tag v-if="row.quick_examination" type="success" size="small">是</el-tag>
            <span v-else>—</span>
          </template>
        </el-table-column>
        <el-table-column label="优审" width="70" align="center">
          <template #default="{ row }">
            <el-tag v-if="row.expedited_examination" type="warning" size="small">是</el-tag>
            <span v-else>—</span>
          </template>
        </el-table-column>
        <el-table-column prop="fee_reduction" label="费减" width="70">
          <template #default="{ row }">
            <el-tag v-if="row.fee_reduction" type="warning" size="small">{{ row.fee_reduction_rate || '是' }}</el-tag>
            <span v-else>—</span>
          </template>
        </el-table-column>
        <el-table-column prop="agency_name" label="代理机构" width="140" show-overflow-tooltip />
        <el-table-column prop="is_pct" label="PCT" width="60">
          <template #default="{ row }">
            <el-tag v-if="row.is_pct" type="danger" size="small">PCT</el-tag>
            <span v-else>—</span>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="140" fixed="right" align="center">
          <template #default="{ row }">
            <div class="action-btns">
              <el-tooltip content="详情" placement="top">
                <el-button circle size="small" type="primary" plain @click="goDetail(row.id)">
                  <el-icon><View /></el-icon>
                </el-button>
              </el-tooltip>
              <el-tooltip content="编辑" placement="top">
                <el-button circle size="small" type="warning" plain @click="openEdit(row)">
                  <el-icon><Edit /></el-icon>
                </el-button>
              </el-tooltip>
              <el-tooltip content="删除" placement="top">
                <el-button circle size="small" type="danger" plain @click="handleDelete(row)">
                  <el-icon><Delete /></el-icon>
                </el-button>
              </el-tooltip>
            </div>
          </template>
        </el-table-column>
      </el-table>

      <el-pagination
        v-model:current-page="page"
        v-model:page-size="pageSize"
        :total="total"
        :page-sizes="[20, 50, 100]"
        layout="total, sizes, prev, pager, next"
        style="margin-top:16px;justify-content:flex-end"
        @size-change="loadData"
        @current-change="loadData"
      />
    </el-card>

    <!-- Create/Edit Dialog -->
    <el-dialog v-model="dialogVisible" :title="editing ? '编辑专利' : '新增专利'" width="800px" :close-on-click-modal="false">
      <el-form :model="form" label-width="100px" class="patent-form">
        <el-row :gutter="16">
          <el-col :span="12"><el-form-item label="申请号"><el-input v-model="form.application_no" /></el-form-item></el-col>
          <el-col :span="12"><el-form-item label="专利名称"><el-input v-model="form.patent_name" /></el-form-item></el-col>
          <el-col :span="12">
            <el-form-item label="类型">
              <el-select v-model="form.patent_type" style="width:100%">
                <el-option v-for="t in patentTypes" :key="t" :label="t" :value="t" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="状态">
              <el-select v-model="form.status" style="width:100%">
                <el-option v-for="s in patentStatuses" :key="s" :label="s" :value="s" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12"><el-form-item label="申请日"><el-date-picker v-model="form.application_date" type="date" value-format="YYYY-MM-DD" style="width:100%" /></el-form-item></el-col>
          <el-col :span="12"><el-form-item label="授权号"><el-input v-model="form.authorization_no" placeholder="专利授权号" /></el-form-item></el-col>
          <el-col :span="12"><el-form-item label="授权日"><el-date-picker v-model="form.authorization_date" type="date" value-format="YYYY-MM-DD" style="width:100%" /></el-form-item></el-col>
          <el-col :span="12"><el-form-item label="发明人"><el-input v-model="form.inventors" placeholder="多人用逗号分隔" /></el-form-item></el-col>
          <el-col :span="12"><el-form-item label="权利人"><el-input v-model="form.applicant" /></el-form-item></el-col>
          <el-col :span="12"><el-form-item label="IPC分类号"><el-input v-model="form.ipc_classification" /></el-form-item></el-col>
          <el-col :span="12"><el-form-item label="对应项目"><el-input v-model="form.correspondence_project" /></el-form-item></el-col>
          <el-col :span="12"><el-form-item label="对应产品"><el-input v-model="form.correspondence_product" /></el-form-item></el-col>
          <el-col :span="12">
            <el-form-item label="代理机构">
              <el-select v-model="form.agency_id" style="width:100%" clearable>
                <el-option v-for="a in agencies" :key="a.id" :label="a.agency_name" :value="a.id" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12"><el-form-item label="代理案件号"><el-input v-model="form.agency_case_no" /></el-form-item></el-col>
          <el-col :span="12"><el-form-item label="官费"><el-input-number v-model="form.official_fee" :precision="2" style="width:100%" /></el-form-item></el-col>
          <el-col :span="12"><el-form-item label="代理费"><el-input-number v-model="form.agency_fee" :precision="2" style="width:100%" /></el-form-item></el-col>
          <el-col :span="12"><el-form-item label="预审费"><el-input-number v-model="form.pre_examination_fee" :precision="2" style="width:100%" /></el-form-item></el-col>
          <el-col :span="8"><el-form-item label="快速预审"><el-switch v-model="form.quick_examination" /></el-form-item></el-col>
          <el-col :span="8"><el-form-item label="优审"><el-switch v-model="form.expedited_examination" /></el-form-item></el-col>
          <el-col :span="8"><el-form-item label="PCT"><el-switch v-model="form.is_pct" /></el-form-item></el-col>
          <el-col :span="12"><el-form-item label="费减"><el-switch v-model="form.fee_reduction" /></el-form-item></el-col>
          <el-col :span="12">
            <el-form-item label="费减比例">
              <el-select v-model="form.fee_reduction_rate" style="width:100%" :disabled="!form.fee_reduction">
                <el-option label="85%" value="85%" />
                <el-option label="70%" value="70%" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="24"><el-form-item label="保护要素"><el-input v-model="form.protection_element" type="textarea" :rows="2" /></el-form-item></el-col>
        </el-row>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="handleSave">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted, computed } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { View, Edit, Delete, Search, Plus, Upload } from '@element-plus/icons-vue'
import api from '../../api'

const router = useRouter()
const loading = ref(false)
const saving = ref(false)
const tableData = ref([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)
const agencies = ref([])
const dialogVisible = ref(false)
const editing = ref(false)

const patentTypes = ['发明', '实用新型', '外观', '软产', '软著']
// 法律状态（用户确认）：驳回复审、驳回终止、撤回、审中、授权、转让
const patentStatuses = ['驳回复审', '驳回终止', '撤回', '审中', '授权', '转让']

const filters = reactive({ search: '', patent_type: '', status: '', apply_year: '', grant_year: '' })
// 年度选项由列表接口返回（数据库中实际存在的年份）
const applyYearOptions = ref([])
const grantYearOptions = ref([])
const yearOptions = computed(() => {
  const set = new Set([...applyYearOptions.value, ...grantYearOptions.value])
  return [...set].sort((a, b) => b - a)
})

const emptyForm = () => ({
  application_no: '', patent_name: '', patent_type: '发明', status: '审中',
  application_date: null, authorization_no: '', authorization_date: null, first_publication_date: null,
  applicant: '示例科技有限公司', inventors: '', ipc_classification: '',
  correspondence_project: '', correspondence_product: '', protection_element: '',
  quick_examination: false, expedited_examination: false, fee_reduction: false,
  fee_reduction_rate: '', official_fee: null, agency_fee: null, pre_examination_fee: null,
  agency_id: null, agency_case_no: '', is_pct: false, description: ''
})
const form = ref(emptyForm())

const typeTagType = (t) => ({ '发明': 'primary', '实用新型': 'success', '外观': 'warning', '软著': 'info', '软产': 'danger' }[t] || '')
const statusTagType = (s) => ({ '授权': 'success', '转让': 'success', '驳回': 'danger', '驳回终止': 'danger', '驳回复审': 'warning', '撤回': 'info', '审中': 'warning' }[s] || '')

const loadData = async () => {
  loading.value = true
  try {
    const params = { page: page.value, page_size: pageSize.value }
    for (const [k, v] of Object.entries(filters)) {
      if (v !== '' && v !== null && v !== undefined) params[k] = v
    }
    const res = await api.get('/patents', { params })
    tableData.value = res.items
    total.value = res.total
    if (res.apply_years) applyYearOptions.value = res.apply_years
    if (res.grant_years) grantYearOptions.value = res.grant_years
  } catch (e) { console.error(e) } finally { loading.value = false }
}

const loadAgencies = async () => {
  try {
    const res = await api.get('/agencies')
    agencies.value = res.items
  } catch (e) { console.error(e) }
}

const goDetail = (id) => router.push(`/patent/${id}`)
const rowDblClick = (row) => goDetail(row.id)

const openCreate = () => {
  form.value = emptyForm()
  editing.value = false
  dialogVisible.value = true
}

// 导入 Excel
const importInput = ref(null)
const importing = ref(false)
const triggerImport = () => { importInput.value?.click() }
const handleImportFile = async (e) => {
  const file = e.target.files[0]
  if (!file) return
  importing.value = true
  const fd = new FormData()
  fd.append('file', file)
  try {
    const res = await api.post('/io/import/patents', fd, { headers: { 'Content-Type': 'multipart/form-data' } })
    ElMessage.success(res.message || '导入完成')
    loadData()
  } catch (err) {
    ElMessage.error('导入失败：' + (err?.message || '请检查文件格式'))
  } finally {
    importing.value = false
    e.target.value = ''
  }
}

const openEdit = (row) => {
  form.value = { ...emptyForm(), ...row }
  editing.value = true
  dialogVisible.value = true
}

const handleSave = async () => {
  if (!form.value.application_no || !form.value.patent_name) {
    ElMessage.warning('请填写申请号和专利名称')
    return
  }
  saving.value = true
  try {
    if (editing.value) {
      await api.put(`/patents/${form.value.id}`, form.value)
      ElMessage.success('更新成功')
    } else {
      await api.post('/patents', form.value)
      ElMessage.success('创建成功')
    }
    dialogVisible.value = false
    loadData()
  } catch (e) { console.error(e) } finally { saving.value = false }
}

const handleDelete = (row) => {
  ElMessageBox.confirm(`确定删除专利「${row.patent_name}」吗？`, '确认删除', { type: 'warning' })
    .then(async () => {
      await api.delete(`/patents/${row.id}`)
      ElMessage.success('已删除')
      loadData()
    }).catch(() => {})
}

onMounted(() => {
  loadData()
  loadAgencies()
})
</script>

<style scoped>
.filter-bar { border-radius: 4px; }
.filter-bar .el-select { width: 100%; }
.action-btns { display: flex; gap: 6px; justify-content: center; }
.filter-row { display: flex; justify-content: space-between; align-items: center; gap: 12px; flex-wrap: nowrap; }
.filter-left { display: flex; gap: 12px; align-items: center; flex-wrap: wrap; flex: 1; }
.filter-right { display: flex; gap: 8px; flex-shrink: 0; align-items: center; }
.filter-bar { margin-bottom: 16px; }
</style>
