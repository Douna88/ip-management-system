<template>
  <div>
    <el-card shadow="never" class="filter-bar">
      <el-row :gutter="16">
        <el-col :span="8"><el-input v-model="filters.search" placeholder="搜索商标名称/注册号/申请人" prefix-icon="Search" clearable @clear="loadData" @keyup.enter="loadData" /></el-col>
        <el-col :span="5">
          <el-select v-model="filters.scope_group" placeholder="注册范围" clearable @change="loadData">
            <el-option label="运动台" value="运动台" /><el-option label="光学传感" value="光学传感" /><el-option label="电子" value="电子" /><el-option label="其他" value="其他" />
          </el-select>
        </el-col>
        <el-col :span="5">
          <el-select v-model="filters.status" placeholder="状态" clearable @change="loadData">
            <el-option v-for="s in tmStatuses" :key="s" :label="s" :value="s" />
          </el-select>
        </el-col>
        <el-col :span="6" style="text-align:right">
          <el-button type="primary" @click="loadData">查询</el-button>
          <el-button type="success" @click="openCreate">新增商标</el-button>
        </el-col>
      </el-row>
    </el-card>

    <el-card shadow="never" style="margin-top:12px">
      <el-table :data="tableData" v-loading="loading" border stripe @row-dblclick="row => $router.push(`/trademark/${row.id}`)">
        <el-table-column label="图形" width="70" align="center">
          <template #default="{ row }">
            <el-image
              v-if="row.logo_url"
              :src="row.logo_url"
              :preview-src-list="[row.logo_url]"
              fit="contain"
              style="width: 40px; height: 40px; cursor: pointer"
              :preview-teleported="true"
            />
            <span v-else style="color:#c0c4cc; font-size:12px">无图</span>
          </template>
        </el-table-column>
        <el-table-column prop="trademark_no" label="注册号" width="120" />
        <el-table-column prop="trademark_name" label="商标名称" min-width="180">
          <template #default="{ row }"><el-link type="primary" @click="$router.push(`/trademark/${row.id}`)">{{ row.trademark_name }}</el-link></template>
        </el-table-column>
        <el-table-column prop="trademark_type" label="类型" width="100" />
        <el-table-column prop="scope_group" label="注册范围" width="100"><template #default="{row}"><el-tag size="small">{{ row.scope_group || '—' }}</el-tag></template></el-table-column>
        <el-table-column prop="nice_class" label="尼斯分类" width="100" />
        <el-table-column prop="application_date" label="申请日" width="110" />
        <el-table-column prop="registration_date" label="注册日" width="110" />
        <el-table-column prop="valid_until" label="有效期至" width="110">
          <template #default="{row}"><span :style="isExpiringSoon(row.valid_until) ? 'color:#F56C6C;font-weight:bold' : ''">{{ row.valid_until }}</span></template>
        </el-table-column>
        <el-table-column prop="status" label="状态" width="90">
          <template #default="{row}"><el-tag :type="tmStatusType(row.status)" size="small">{{ row.status }}</el-tag></template>
        </el-table-column>
        <el-table-column prop="applicant" label="申请人" min-width="200" show-overflow-tooltip />
        <el-table-column prop="agency_name" label="代理机构" width="140" show-overflow-tooltip />
        <el-table-column label="操作" width="140" fixed="right" align="center">
          <template #default="{row}">
            <div class="action-btns">
              <el-tooltip content="详情" placement="top">
                <el-button circle size="small" type="primary" plain @click="$router.push(`/trademark/${row.id}`)">
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
      <el-pagination v-model:current-page="page" v-model:page-size="pageSize" :total="total" :page-sizes="[20,50,100]" layout="total, sizes, prev, pager, next" style="margin-top:16px;justify-content:flex-end" @size-change="loadData" @current-change="loadData" />
    </el-card>

    <el-dialog v-model="dialogVisible" :title="editing ? '编辑商标' : '新增商标'" width="700px" :close-on-click-modal="false">
      <el-form :model="form" label-width="100px">
        <el-form-item label="商标图形">
          <el-upload
            :show-file-list="false"
            :before-upload="beforeLogoUpload"
            :http-request="handleLogoUpload"
            accept="image/*"
          >
            <el-image
              v-if="form.logo_url"
              :src="form.logo_url"
              fit="contain"
              style="width: 80px; height: 80px; border: 1px solid #dcdfe6; border-radius: 4px"
            />
            <el-button v-else type="primary" plain size="small">点击上传图形</el-button>
          </el-upload>
          <el-button v-if="form.logo_url" type="danger" size="small" link @click="removeLogo" style="margin-left: 12px">移除</el-button>
        </el-form-item>
        <el-row :gutter="16">
          <el-col :span="12"><el-form-item label="注册号"><el-input v-model="form.trademark_no" /></el-form-item></el-col>
          <el-col :span="12"><el-form-item label="商标名称"><el-input v-model="form.trademark_name" /></el-form-item></el-col>
          <el-col :span="12"><el-form-item label="类型"><el-select v-model="form.trademark_type" style="width:100%"><el-option label="文字" value="文字" /><el-option label="图形" value="图形" /><el-option label="文字+图形" value="文字+图形" /></el-select></el-form-item></el-col>
          <el-col :span="12"><el-form-item label="注册范围"><el-select v-model="form.scope_group" style="width:100%"><el-option label="运动台" value="运动台" /><el-option label="光学传感" value="光学传感" /><el-option label="电子" value="电子" /><el-option label="其他" value="其他" /></el-select></el-form-item></el-col>
          <el-col :span="12"><el-form-item label="尼斯分类"><el-input v-model="form.nice_class" placeholder="多个用逗号分隔，如 9,28,42" /></el-form-item></el-col>
          <el-col :span="12"><el-form-item label="状态"><el-select v-model="form.status" style="width:100%"><el-option v-for="s in tmStatuses" :key="s" :label="s" :value="s" /></el-select></el-form-item></el-col>
          <el-col :span="12"><el-form-item label="申请日"><el-date-picker v-model="form.application_date" type="date" value-format="YYYY-MM-DD" style="width:100%" /></el-form-item></el-col>
          <el-col :span="12"><el-form-item label="注册日"><el-date-picker v-model="form.registration_date" type="date" value-format="YYYY-MM-DD" style="width:100%" /></el-form-item></el-col>
          <el-col :span="12"><el-form-item label="有效期至"><el-date-picker v-model="form.valid_until" type="date" value-format="YYYY-MM-DD" style="width:100%" /></el-form-item></el-col>
          <el-col :span="12"><el-form-item label="申请人"><el-input v-model="form.applicant" /></el-form-item></el-col>
          <el-col :span="12"><el-form-item label="代理机构"><el-select v-model="form.agency_id" style="width:100%" clearable><el-option v-for="a in agencies" :key="a.id" :label="a.agency_name" :value="a.id" /></el-select></el-form-item></el-col>
          <el-col :span="12"><el-form-item label="联系人"><el-input v-model="form.contact_person" /></el-form-item></el-col>
          <el-col :span="24"><el-form-item label="备注"><el-input v-model="form.notes" type="textarea" :rows="2" /></el-form-item></el-col>
        </el-row>
      </el-form>
      <template #footer><el-button @click="dialogVisible = false">取消</el-button><el-button type="primary" :loading="saving" @click="handleSave">保存</el-button></template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { View, Edit, Delete } from '@element-plus/icons-vue'
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

const tmStatuses = ['申请中', '已注册', '驳回', '已续展', '已失效', '部分授权', '审中', '授权']
const filters = reactive({ search: '', scope_group: '', status: '' })

const emptyForm = () => ({
  trademark_no: '', trademark_name: '', trademark_type: '文字', application_date: null,
  registration_date: null, valid_until: null, nice_class: '', scope_group: '运动台',
  applicant: '示例科技有限公司', agency_id: null, status: '申请中',
  partial_grant_class: '', renewal_count: 0, contact_person: '', notes: '',
  logo_file_id: null, logo_url: ''
})
const form = ref(emptyForm())

// Logo upload
const beforeLogoUpload = (file) => {
  const isImage = file.type.startsWith('image/')
  const isLt5M = file.size / 1024 / 1024 < 5
  if (!isImage) { ElMessage.error('只能上传图片文件'); return false }
  if (!isLt5M) { ElMessage.error('图片大小不能超过 5MB'); return false }
  return true
}
const handleLogoUpload = async (options) => {
  const formData = new FormData()
  formData.append('file', options.file)
  formData.append('business_type', 'trademark')
  formData.append('business_id', form.value.id || '0')
  try {
    const res = await api.post('/files/upload', formData, { headers: { 'Content-Type': 'multipart/form-data' } })
    form.value.logo_file_id = res.id
    form.value.logo_url = `/uploads/${res.storage_path}`
    ElMessage.success('图形上传成功')
  } catch (e) { ElMessage.error('上传失败') }
}
const removeLogo = () => {
  form.value.logo_file_id = null
  form.value.logo_url = ''
}

const tmStatusType = (s) => ({ '已注册': 'success', '已续展': 'success', '授权': 'success', '申请中': 'warning', '审中': 'warning', '驳回': 'danger', '已失效': 'danger', '部分授权': 'info' }[s] || '')
const isExpiringSoon = (dateStr) => {
  if (!dateStr) return false
  const diff = new Date(dateStr) - new Date()
  return diff > 0 && diff < 365 * 24 * 60 * 60 * 1000
}

const loadData = async () => {
  loading.value = true
  try {
    const res = await api.get('/trademarks', { params: { ...filters, page: page.value, page_size: pageSize.value } })
    tableData.value = res.items
    total.value = res.total
  } catch (e) {} finally { loading.value = false }
}

const openCreate = () => { form.value = emptyForm(); editing.value = false; dialogVisible.value = true }
const openEdit = (row) => { form.value = { ...emptyForm(), ...row }; editing.value = true; dialogVisible.value = true }

const handleSave = async () => {
  if (!form.value.trademark_name) { ElMessage.warning('请填写商标名称'); return }
  saving.value = true
  try {
    if (editing.value) { await api.put(`/trademarks/${form.value.id}`, form.value); ElMessage.success('更新成功') }
    else { await api.post('/trademarks', form.value); ElMessage.success('创建成功') }
    dialogVisible.value = false; loadData()
  } catch (e) {} finally { saving.value = false }
}

const handleDelete = (row) => {
  ElMessageBox.confirm(`确定删除商标「${row.trademark_name}」？`, '确认', { type: 'warning' })
    .then(async () => { await api.delete(`/trademarks/${row.id}`); ElMessage.success('已删除'); loadData() }).catch(() => {})
}

onMounted(() => { loadData(); api.get('/agencies').then(r => agencies.value = r.items).catch(() => {}) })
</script>

<style scoped>
.filter-bar .el-select { width: 100%; }
.action-btns { display: flex; gap: 6px; justify-content: center; }
</style>
