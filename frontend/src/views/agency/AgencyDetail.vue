<template>
  <div v-loading="loading">
    <!-- Header -->
    <el-card style="margin-bottom: 16px">
      <div style="display: flex; justify-content: space-between; align-items: center">
        <div>
          <el-page-header @back="$router.push('/agency')" :title="'返回'" :content="agency.agency_name || '详情'" />
        </div>
        <div>
          <el-button type="primary" @click="editDialog = true">编辑信息</el-button>
        </div>
      </div>
    </el-card>

    <!-- Stats cards -->
    <el-row :gutter="16" style="margin-bottom: 16px">
      <el-col :span="6">
        <el-card shadow="hover"><el-statistic title="代理专利" :value="agency.patent_count || 0" /></el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover"><el-statistic title="代理商标" :value="agency.trademark_count || 0" /></el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover"><el-statistic title="累计金额" :value="agency.total_amount || 0" prefix="¥" :precision="0" /></el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover"><el-statistic title="本年金额" :value="agency.this_year_amount || 0" prefix="¥" :precision="0" /></el-card>
      </el-col>
    </el-row>

    <el-tabs v-model="activeTab">
      <!-- Basic Info -->
      <el-tab-pane label="基本信息" name="info">
        <el-card>
          <el-descriptions :column="2" border>
            <el-descriptions-item label="机构名称">{{ agency.agency_name }}</el-descriptions-item>
            <el-descriptions-item label="联系人">{{ agency.contact_person || '—' }}</el-descriptions-item>
            <el-descriptions-item label="电话">{{ agency.contact_phone || '—' }}</el-descriptions-item>
            <el-descriptions-item label="邮箱">{{ agency.email || '—' }}</el-descriptions-item>
            <el-descriptions-item label="地址">{{ agency.address || '—' }}</el-descriptions-item>
            <el-descriptions-item label="业务范围">
              <el-tag v-for="s in (agency.business_scope || '').split(',')" :key="s" size="small" style="margin-right: 4px">{{ s }}</el-tag>
            </el-descriptions-item>
            <el-descriptions-item label="合作开始">{{ agency.cooperation_start || '—' }}</el-descriptions-item>
            <el-descriptions-item label="合作结束">{{ agency.cooperation_end || '—' }}</el-descriptions-item>
            <el-descriptions-item label="状态">
              <el-tag :type="agency.status === '合作中' ? 'success' : 'warning'">{{ agency.status }}</el-tag>
            </el-descriptions-item>
            <el-descriptions-item label="去年金额">¥{{ (agency.last_year_amount || 0).toLocaleString() }}</el-descriptions-item>
            <el-descriptions-item label="备注" :span="2">{{ agency.notes || '—' }}</el-descriptions-item>
          </el-descriptions>
        </el-card>
      </el-tab-pane>

      <!-- Files -->
      <el-tab-pane label="合同与文件" name="files">
        <el-card>
          <template #header>
            <div style="display: flex; justify-content: space-between; align-items: center">
              <span>合同及价目表文件</span>
              <el-upload :show-file-list="false" :http-request="handleUploadFile" :before-upload="beforeUpload">
                <el-button type="primary" size="small" :icon="Upload">上传文件</el-button>
              </el-upload>
            </div>
          </template>
          <el-table :data="agency.files || []" stripe>
            <el-table-column label="文件名" prop="original_name" min-width="200" show-overflow-tooltip />
            <el-table-column label="类型" prop="file_type" width="80" />
            <el-table-column label="大小" width="100">
              <template #default="{ row }">{{ formatSize(row.file_size) }}</template>
            </el-table-column>
            <el-table-column label="上传时间" prop="uploaded_at" width="160" />
            <el-table-column label="操作" width="120" align="center">
              <template #default="{ row }">
                <div class="action-btns">
                  <el-tooltip content="下载" placement="top">
                    <el-button circle size="small" type="primary" plain @click="downloadFile(row)">
                      <el-icon><Download /></el-icon>
                    </el-button>
                  </el-tooltip>
                </div>
              </template>
            </el-table-column>
          </el-table>
          <el-empty v-if="!(agency.files && agency.files.length)" description="暂无文件" />
        </el-card>
      </el-tab-pane>

      <!-- Price Changes -->
      <el-tab-pane label="费用调整记录" name="changes">
        <el-card>
          <template #header>
            <div style="display: flex; justify-content: space-between; align-items: center">
              <span>费用调整历史</span>
              <el-button type="primary" size="small" @click="changeDialog = true">添加调整记录</el-button>
            </div>
          </template>
          <el-table :data="agency.price_changes || []" stripe>
            <el-table-column label="调整日期" prop="change_date" width="120" />
            <el-table-column label="服务项" prop="service_item" min-width="150" />
            <el-table-column label="原价" width="100" align="right">
              <template #default="{ row }">¥{{ row.old_price || 0 }}</template>
            </el-table-column>
            <el-table-column label="新价" width="100" align="right">
              <template #default="{ row }">
                <span :style="{ color: row.new_price > row.old_price ? '#F56C6C' : '#67C23A' }">¥{{ row.new_price || 0 }}</span>
              </template>
            </el-table-column>
            <el-table-column label="调整原因" prop="change_reason" min-width="150" show-overflow-tooltip />
            <el-table-column label="生效日期" prop="effective_date" width="120" />
          </el-table>
          <el-empty v-if="!(agency.price_changes && agency.price_changes.length)" description="暂无调整记录" />
        </el-card>
      </el-tab-pane>

      <!-- Related Patents -->
      <el-tab-pane label="关联专利" name="patents">
        <el-card>
          <el-table :data="agency.related_patents || []" stripe @row-click="(row) => $router.push(`/patent/${row.id}`)" style="cursor: pointer">
            <el-table-column label="申请号" prop="application_no" width="160" />
            <el-table-column label="专利名称" prop="patent_name" min-width="200" show-overflow-tooltip />
            <el-table-column label="类型" prop="patent_type" width="100" />
            <el-table-column label="状态" prop="status" width="100">
              <template #default="{ row }">
                <el-tag :type="statusTag(row.status)" size="small">{{ row.status }}</el-tag>
              </template>
            </el-table-column>
          </el-table>
          <el-empty v-if="!(agency.related_patents && agency.related_patents.length)" description="暂无关联专利" />
        </el-card>
      </el-tab-pane>

      <!-- Price Comparison -->
      <el-tab-pane label="横向比价" name="compare">
        <el-card>
          <template #header>代理机构横向价格对比（最新价格）</template>
          <el-table :data="compareData.matrix || []" stripe border>
            <el-table-column label="服务项" prop="service_item" min-width="180" fixed />
            <el-table-column v-for="ag in compareData.agencies" :key="ag" :label="ag" width="130" align="right">
              <template #default="{ row }">
                <span v-if="row[ag] != null">¥{{ row[ag] }}</span>
                <span v-else style="color: #c0c4cc">—</span>
              </template>
            </el-table-column>
          </el-table>
          <el-empty v-if="!(compareData.matrix && compareData.matrix.length)" description="暂无比价数据" />
        </el-card>
      </el-tab-pane>
    </el-tabs>

    <!-- Edit Dialog -->
    <el-dialog v-model="editDialog" title="编辑代理机构" width="600px">
      <el-form :model="editForm" label-width="100px">
        <el-form-item label="机构名称"><el-input v-model="editForm.agency_name" /></el-form-item>
        <el-form-item label="联系人"><el-input v-model="editForm.contact_person" /></el-form-item>
        <el-form-item label="电话"><el-input v-model="editForm.contact_phone" /></el-form-item>
        <el-form-item label="邮箱"><el-input v-model="editForm.email" /></el-form-item>
        <el-form-item label="地址"><el-input v-model="editForm.address" /></el-form-item>
        <el-form-item label="业务范围"><el-input v-model="editForm.business_scope" placeholder="专利,商标,PCT" /></el-form-item>
        <el-form-item label="合作开始"><el-date-picker v-model="editForm.cooperation_start" type="date" value-format="YYYY-MM-DD" /></el-form-item>
        <el-form-item label="合作结束"><el-date-picker v-model="editForm.cooperation_end" type="date" value-format="YYYY-MM-DD" /></el-form-item>
        <el-form-item label="状态">
          <el-select v-model="editForm.status">
            <el-option label="合作中" value="合作中" />
            <el-option label="暂停" value="暂停" />
            <el-option label="已终止" value="已终止" />
          </el-select>
        </el-form-item>
        <el-form-item label="备注"><el-input v-model="editForm.notes" type="textarea" :rows="2" /></el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="editDialog = false">取消</el-button>
        <el-button type="primary" @click="handleSave">保存</el-button>
      </template>
    </el-dialog>

    <!-- Price Change Dialog -->
    <el-dialog v-model="changeDialog" title="添加费用调整记录" width="500px">
      <el-form :model="changeForm" label-width="100px">
        <el-form-item label="调整日期"><el-date-picker v-model="changeForm.change_date" type="date" value-format="YYYY-MM-DD" /></el-form-item>
        <el-form-item label="服务项"><el-input v-model="changeForm.service_item" placeholder="如：发明申请代理费" /></el-form-item>
        <el-form-item label="原价"><el-input-number v-model="changeForm.old_price" :min="0" :precision="2" /></el-form-item>
        <el-form-item label="新价"><el-input-number v-model="changeForm.new_price" :min="0" :precision="2" /></el-form-item>
        <el-form-item label="调整原因"><el-input v-model="changeForm.change_reason" type="textarea" :rows="2" /></el-form-item>
        <el-form-item label="生效日期"><el-date-picker v-model="changeForm.effective_date" type="date" value-format="YYYY-MM-DD" /></el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="changeDialog = false">取消</el-button>
        <el-button type="primary" @click="handleSaveChange">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import { Upload, Download } from '@element-plus/icons-vue'
import api from '@/api'

const route = useRoute()
const agencyId = route.params.id
const loading = ref(false)
const activeTab = ref('info')
const agency = ref({})
const compareData = ref({})
const editDialog = ref(false)
const changeDialog = ref(false)

const editForm = reactive({})
const changeForm = reactive({
  change_date: '', service_item: '', old_price: 0, new_price: 0,
  change_reason: '', effective_date: ''
})

const loadData = async () => {
  loading.value = true
  try {
    const res = await api.get(`/agencies/${agencyId}`)
    agency.value = res
    Object.assign(editForm, res)
  } catch (e) { console.error(e) } finally {
    loading.value = false
  }
}

const loadCompare = async () => {
  try {
    const res = await api.get('/admin/agency-price-compare')
    compareData.value = res
  } catch (e) { console.error(e) }
}

const handleSave = async () => {
  try {
    await api.put(`/agencies/${agencyId}`, editForm)
    ElMessage.success('保存成功')
    editDialog.value = false
    loadData()
  } catch (e) { console.error(e) }
}

const handleSaveChange = async () => {
  try {
    await api.post(`/agencies/${agencyId}/price-changes`, { ...changeForm, agency_id: parseInt(agencyId) })
    ElMessage.success('添加成功')
    changeDialog.value = false
    Object.assign(changeForm, { change_date: '', service_item: '', old_price: 0, new_price: 0, change_reason: '', effective_date: '' })
    loadData()
  } catch (e) { console.error(e) }
}

const beforeUpload = (file) => file.size <= 100 * 1024 * 1024

const handleUploadFile = async ({ file }) => {
  const formData = new FormData()
  formData.append('file', file)
  formData.append('business_type', 'agency')
  formData.append('business_id', agencyId)
  try {
    await api.post('/files/upload', formData, { headers: { 'Content-Type': 'multipart/form-data' } })
    ElMessage.success('上传成功')
    loadData()
  } catch (e) { console.error(e) }
}

const downloadFile = (row) => window.open(`/api/files/${row.id}/download?token=${localStorage.getItem('token')}`, '_blank')

const formatSize = (bytes) => {
  if (!bytes) return '—'
  if (bytes < 1024) return bytes + ' B'
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB'
  return (bytes / 1024 / 1024).toFixed(1) + ' MB'
}

const statusTag = (status) => {
  const map = { 授权: 'success', 转让: 'success', 驳回终止: 'danger', 驳回复审: 'warning', 撤回: 'info', 审中: 'warning' }
  return map[status] || ''
}

onMounted(() => {
  loadData()
  loadCompare()
})
</script>

<style scoped>
.action-btns { display: flex; gap: 6px; justify-content: center; }
</style>
