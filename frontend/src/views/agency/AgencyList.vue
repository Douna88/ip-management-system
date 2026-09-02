<template>
  <div>
    <el-card shadow="never" class="filter-bar">
      <el-row :gutter="16">
        <el-col :span="12"><el-input v-model="search" placeholder="搜索机构名称/联系人" prefix-icon="Search" clearable @clear="loadData" @keyup.enter="loadData" /></el-col>
        <el-col :span="12" style="text-align:right"><el-button type="primary" @click="loadData">查询</el-button><el-button type="success" @click="openCreate">新增机构</el-button></el-col>
      </el-row>
    </el-card>

    <el-card shadow="never" style="margin-top:12px">
      <el-table :data="tableData" v-loading="loading" border stripe @row-dblclick="row => $router.push(`/agency/${row.id}`)">
        <el-table-column prop="agency_name" label="机构名称" min-width="200"><template #default="{row}"><el-link type="primary" @click="openDetail(row.id)">{{ row.agency_name }}</el-link></template></el-table-column>
        <el-table-column prop="contact_person" label="联系人" width="100" />
        <el-table-column prop="contact_phone" label="电话" width="130" />
        <el-table-column prop="business_scope" label="业务范围" width="120" show-overflow-tooltip />
        <el-table-column prop="cooperation_start" label="合作开始" width="110" />
        <el-table-column prop="status" label="状态" width="80"><template #default="{row}"><el-tag :type="row.status==='合作中'?'success':'info'" size="small">{{ row.status }}</el-tag></template></el-table-column>
        <el-table-column prop="patent_count" label="专利数" width="80" />
        <el-table-column prop="trademark_count" label="商标数" width="80" />
        <el-table-column prop="total_amount" label="累计金额" width="120"><template #default="{row}">¥{{ formatNum(row.total_amount) }}</template></el-table-column>
        <el-table-column prop="this_year_amount" label="本年金额" width="120"><template #default="{row}">¥{{ formatNum(row.this_year_amount) }}</template></el-table-column>
        <el-table-column label="操作" width="140" fixed="right" align="center">
          <template #default="{row}">
            <div class="action-btns">
              <el-tooltip content="详情" placement="top">
                <el-button circle size="small" type="primary" plain @click="openDetail(row.id)">
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
    </el-card>

    <el-dialog v-model="dialogVisible" :title="editing ? '编辑机构' : '新增机构'" width="600px">
      <el-form :model="form" label-width="100px">
        <el-form-item label="机构名称"><el-input v-model="form.agency_name" /></el-form-item>
        <el-row :gutter="16">
          <el-col :span="12"><el-form-item label="联系人"><el-input v-model="form.contact_person" /></el-form-item></el-col>
          <el-col :span="12"><el-form-item label="电话"><el-input v-model="form.contact_phone" /></el-form-item></el-col>
          <el-col :span="12"><el-form-item label="邮箱"><el-input v-model="form.email" /></el-form-item></el-col>
          <el-col :span="12"><el-form-item label="状态"><el-select v-model="form.status" style="width:100%"><el-option label="合作中" value="合作中" /><el-option label="暂停" value="暂停" /><el-option label="已终止" value="已终止" /></el-select></el-form-item></el-col>
        </el-row>
        <el-form-item label="地址"><el-input v-model="form.address" /></el-form-item>
        <el-form-item label="业务范围"><el-input v-model="form.business_scope" placeholder="专利,商标,PCT" /></el-form-item>
        <el-row :gutter="16">
          <el-col :span="12"><el-form-item label="合作开始"><el-date-picker v-model="form.cooperation_start" type="date" value-format="YYYY-MM-DD" style="width:100%" /></el-form-item></el-col>
          <el-col :span="12"><el-form-item label="合作结束"><el-date-picker v-model="form.cooperation_end" type="date" value-format="YYYY-MM-DD" style="width:100%" /></el-form-item></el-col>
        </el-row>
        <el-form-item label="备注"><el-input v-model="form.notes" type="textarea" :rows="2" /></el-form-item>
      </el-form>
      <template #footer><el-button @click="dialogVisible = false">取消</el-button><el-button type="primary" :loading="saving" @click="handleSave">保存</el-button></template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { View, Edit, Delete } from '@element-plus/icons-vue'
import api from '../../api'

const router = useRouter()

const loading = ref(false)
const saving = ref(false)
const tableData = ref([])
const search = ref('')
const dialogVisible = ref(false)
const editing = ref(false)

const emptyForm = () => ({ agency_name: '', contact_person: '', contact_phone: '', email: '', address: '', business_scope: '', cooperation_start: null, cooperation_end: null, status: '合作中', notes: '' })
const form = ref(emptyForm())

const formatNum = (n) => n ? Number(n).toLocaleString('zh-CN', { minimumFractionDigits: 0, maximumFractionDigits: 2 }) : '0'

const loadData = async () => {
  loading.value = true
  try { const res = await api.get('/agencies', { params: { search: search.value } }); tableData.value = res.items } catch (e) {} finally { loading.value = false }
}

const openDetail = (id) => { router.push(`/agency/${id}`) }
const openCreate = () => { form.value = emptyForm(); editing.value = false; dialogVisible.value = true }
const openEdit = (row) => { form.value = { ...emptyForm(), ...row }; editing.value = true; dialogVisible.value = true }

const handleSave = async () => {
  if (!form.value.agency_name) { ElMessage.warning('请填写机构名称'); return }
  saving.value = true
  try {
    if (editing.value) { await api.put(`/agencies/${form.value.id}`, form.value); ElMessage.success('更新成功') }
    else { await api.post('/agencies', form.value); ElMessage.success('创建成功') }
    dialogVisible.value = false; loadData()
  } catch (e) {} finally { saving.value = false }
}

const handleDelete = (row) => { ElMessageBox.confirm(`删除机构「${row.agency_name}」？`, '确认', { type: 'warning' }).then(async () => { await api.delete(`/agencies/${row.id}`); ElMessage.success('已删除'); loadData() }).catch(() => {}) }

onMounted(loadData)
</script>

<style scoped>
.filter-bar { border-radius: 4px; }
.action-btns { display: flex; gap: 6px; justify-content: center; }
</style>
