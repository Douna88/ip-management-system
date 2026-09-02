<template>
  <div v-loading="loading">
    <el-page-header @back="$router.back()" style="margin-bottom:16px">
      <template #content><span style="font-size:16px">{{ tm.trademark_name || '商标详情' }}</span></template>
    </el-page-header>

    <el-tabs v-model="activeTab">
      <!-- Basic Info -->
      <el-tab-pane label="基本信息" name="info">
        <el-row :gutter="16">
          <!-- Logo Preview -->
          <el-col :span="6">
            <el-card shadow="never">
              <template #header>商标图样</template>
              <div class="logo-area">
                <el-image
                  v-if="logoUrl"
                  :src="logoUrl"
                  fit="contain"
                  style="width: 100%; height: 200px; border: 1px solid #ebeef5; border-radius: 4px"
                  :preview-src-list="[logoUrl]"
                />
                <div v-else class="logo-placeholder">
                  <el-icon size="48" color="#c0c4cc"><Picture /></el-icon>
                  <div style="margin-top: 8px; color: #909399; font-size: 13px">暂无图样</div>
                </div>
                <el-upload
                  :action="`/api/files/upload?business_type=trademark&business_id=${tmId}`"
                  :headers="uploadHeaders"
                  :show-file-list="false"
                  accept="image/*"
                  :on-success="onLogoUpload"
                  style="margin-top: 12px"
                >
                  <el-button type="primary" size="small" :icon="UploadFilled">上传商标图样</el-button>
                </el-upload>
              </div>
            </el-card>
          </el-col>

          <!-- Info Table -->
          <el-col :span="18">
            <el-card shadow="never">
              <el-descriptions :column="3" border>
                <el-descriptions-item label="注册号">{{ tm.trademark_no || '—' }}</el-descriptions-item>
                <el-descriptions-item label="商标名称">{{ tm.trademark_name }}</el-descriptions-item>
                <el-descriptions-item label="类型">{{ tm.trademark_type || '—' }}</el-descriptions-item>
                <el-descriptions-item label="注册范围"><el-tag size="small">{{ tm.scope_group || '—' }}</el-tag></el-descriptions-item>
                <el-descriptions-item label="尼斯分类">{{ tm.nice_class || '—' }}</el-descriptions-item>
                <el-descriptions-item label="状态"><el-tag :type="tmStatusType(tm.status)" size="small">{{ tm.status }}</el-tag></el-descriptions-item>
                <el-descriptions-item label="申请日">{{ tm.application_date || '—' }}</el-descriptions-item>
                <el-descriptions-item label="注册日">{{ tm.registration_date || '—' }}</el-descriptions-item>
                <el-descriptions-item label="有效期至"><span :style="isExpiringSoon(tm.valid_until) ? 'color:#F56C6C;font-weight:bold' : ''">{{ tm.valid_until || '—' }}</span></el-descriptions-item>
                <el-descriptions-item label="申请人">{{ tm.applicant || '—' }}</el-descriptions-item>
                <el-descriptions-item label="代理机构">{{ tm.agency_name || '—' }}</el-descriptions-item>
                <el-descriptions-item label="联系人">{{ tm.contact_person || '—' }}</el-descriptions-item>
                <el-descriptions-item label="续展次数">{{ tm.renewal_count || 0 }}</el-descriptions-item>
                <el-descriptions-item label="最近续展日">{{ tm.last_renewal_date || '—' }}</el-descriptions-item>
                <el-descriptions-item label="续展截止日"><span :style="isExpiringSoon(tm.renewal_deadline) ? 'color:#E6A23C;font-weight:bold' : ''">{{ tm.renewal_deadline || '—' }}</span></el-descriptions-item>
                <el-descriptions-item label="宽展截止日">{{ tm.grace_period_deadline || '—' }}</el-descriptions-item>
                <el-descriptions-item label="部分授权分类" :span="2">{{ tm.partial_grant_class || '—' }}</el-descriptions-item>
                <el-descriptions-item label="备注" :span="3">{{ tm.notes || '—' }}</el-descriptions-item>
              </el-descriptions>
            </el-card>
          </el-col>
        </el-row>
      </el-tab-pane>

      <!-- Renewal Timeline -->
      <el-tab-pane label="续展信息" name="renewal">
        <el-card shadow="never">
          <template #header>
            <div style="display: flex; justify-content: space-between; align-items: center">
              <span>续展时间线</span>
              <el-button type="primary" size="small" @click="openRenewalDialog">登记续展</el-button>
            </div>
          </template>

          <!-- Timeline -->
          <el-timeline v-if="renewalEvents.length > 0">
            <el-timeline-item
              v-for="(event, idx) in renewalEvents"
              :key="idx"
              :timestamp="event.date"
              :type="event.type"
              :hollow="event.hollow"
              placement="top"
            >
              <el-card shadow="hover" style="padding: 4px 0">
                <h4 style="margin: 0 0 4px 0">{{ event.title }}</h4>
                <p style="margin: 0; color: #909399; font-size: 13px">{{ event.description }}</p>
              </el-card>
            </el-timeline-item>
          </el-timeline>
          <el-empty v-else description="暂无续展记录" />

          <!-- Renewal status cards -->
          <el-row :gutter="12" style="margin-top: 20px" v-if="tm.valid_until">
            <el-col :span="8">
              <el-card shadow="hover">
                <el-statistic title="距有效期截止" :value="daysUntilValid" suffix="天" />
                <div style="margin-top: 4px">
                  <el-tag :type="daysUntilValid < 0 ? 'danger' : daysUntilValid < 180 ? 'warning' : 'success'" size="small">
                    {{ daysUntilValid < 0 ? '已过期' : daysUntilValid < 180 ? '即将到期' : '有效' }}
                  </el-tag>
                </div>
              </el-card>
            </el-col>
            <el-col :span="8">
              <el-card shadow="hover">
                <el-statistic title="距续展截止" :value="daysUntilRenewal" suffix="天" />
                <div style="margin-top: 4px">
                  <el-tag :type="daysUntilRenewal < 0 ? 'danger' : daysUntilRenewal < 180 ? 'warning' : 'success'" size="small">
                    {{ daysUntilRenewal < 0 ? '已过期' : daysUntilRenewal < 180 ? '需尽快续展' : '可续展' }}
                  </el-tag>
                </div>
              </el-card>
            </el-col>
            <el-col :span="8">
              <el-card shadow="hover">
                <el-statistic title="距宽展截止" :value="daysUntilGrace" suffix="天" />
                <div style="margin-top: 4px">
                  <el-tag :type="daysUntilGrace < 0 ? 'danger' : 'warning'" size="small">
                    {{ daysUntilGrace < 0 ? '宽展已结束' : '宽展期内' }}
                  </el-tag>
                </div>
              </el-card>
            </el-col>
          </el-row>
        </el-card>
      </el-tab-pane>

      <!-- Files -->
      <el-tab-pane label="关联文件" name="files">
        <el-card shadow="never">
          <el-upload :action="`/api/files/upload?business_type=trademark&business_id=${tmId}`" :headers="uploadHeaders" :on-success="() => { ElMessage.success('上传成功'); loadData() }" :show-file-list="false" drag style="margin-bottom:16px">
            <el-icon size="40"><UploadFilled /></el-icon><div>点击或拖拽上传</div>
          </el-upload>
          <el-table :data="tm.files || []" border stripe size="small">
            <el-table-column prop="original_name" label="文件名" min-width="200" />
            <el-table-column prop="file_type" label="类型" width="80" />
            <el-table-column label="大小" width="100"><template #default="{row}">{{ formatSize(row.file_size) }}</template></el-table-column>
            <el-table-column prop="uploaded_at" label="上传时间" width="160" />
            <el-table-column label="操作" width="120" align="center">
              <template #default="{row}">
                <div class="action-btns">
                  <el-tooltip content="下载" placement="top">
                    <el-button circle size="small" type="primary" plain @click="downloadFile(row.id)">
                      <el-icon><Download /></el-icon>
                    </el-button>
                  </el-tooltip>
                  <el-tooltip content="删除" placement="top">
                    <el-button circle size="small" type="danger" plain @click="deleteFile(row.id)">
                      <el-icon><Delete /></el-icon>
                    </el-button>
                  </el-tooltip>
                </div>
              </template>
            </el-table-column>
          </el-table>
        </el-card>
      </el-tab-pane>

      <!-- Audit Log -->
      <el-tab-pane label="操作日志" name="logs">
        <el-card shadow="never">
          <el-table :data="auditLogs" border stripe size="small" v-loading="logsLoading">
            <el-table-column prop="created_at" label="时间" width="160">
              <template #default="{row}">{{ formatDate(row.created_at) }}</template>
            </el-table-column>
            <el-table-column prop="user_name" label="操作人" width="100" />
            <el-table-column prop="action" label="操作" width="80">
              <template #default="{row}">
                <el-tag :type="actionTagType(row.action)" size="small">{{ actionLabel(row.action) }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column label="变更内容" min-width="300">
              <template #default="{row}">
                <div v-if="row.before_value || row.after_value" style="font-size: 12px; color: #909399">
                  <span v-if="row.before_value">变更前: {{ row.before_value }}</span>
                  <span v-if="row.before_value && row.after_value"> → </span>
                  <span v-if="row.after_value">变更后: {{ row.after_value }}</span>
                </div>
                <span v-else style="color: #c0c4cc">—</span>
              </template>
            </el-table-column>
          </el-table>
          <el-pagination
            style="margin-top: 12px; justify-content: flex-end"
            v-model:current-page="logPage.page"
            :page-size="logPage.page_size"
            :total="logPage.total"
            layout="total, prev, pager, next"
            @current-change="loadAuditLogs"
          />
        </el-card>
      </el-tab-pane>
    </el-tabs>

    <!-- Renewal Dialog -->
    <el-dialog v-model="renewalDialogVisible" title="登记续展" width="480px">
      <el-form :model="renewalForm" label-width="110px">
        <el-form-item label="续展日期" required>
          <el-date-picker v-model="renewalForm.last_renewal_date" type="date" value-format="YYYY-MM-DD" style="width: 100%" />
        </el-form-item>
        <el-form-item label="新有效期至" required>
          <el-date-picker v-model="renewalForm.valid_until" type="date" value-format="YYYY-MM-DD" style="width: 100%" />
        </el-form-item>
        <el-form-item label="新续展截止日">
          <el-date-picker v-model="renewalForm.renewal_deadline" type="date" value-format="YYYY-MM-DD" style="width: 100%" />
        </el-form-item>
        <el-form-item label="新宽展截止日">
          <el-date-picker v-model="renewalForm.grace_period_deadline" type="date" value-format="YYYY-MM-DD" style="width: 100%" />
        </el-form-item>
        <el-alert type="info" :closable="false" show-icon>
          续展后，商标状态将自动更新为「已续展」，续展次数 +1。
        </el-alert>
      </el-form>
      <template #footer>
        <el-button @click="renewalDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="saveRenewal">确认续展</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted, watch } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { UploadFilled, Picture, Download, Delete } from '@element-plus/icons-vue'
import api from '../../api'

const route = useRoute()
const tmId = parseInt(route.params.id)
const loading = ref(false)
const activeTab = ref('info')
const tm = ref({})
const uploadHeaders = computed(() => ({ Authorization: `Bearer ${localStorage.getItem('token')}` }))

const auditLogs = ref([])
const logsLoading = ref(false)
const logPage = reactive({ page: 1, page_size: 20, total: 0 })

const renewalDialogVisible = ref(false)
const renewalForm = reactive({
  last_renewal_date: null,
  valid_until: null,
  renewal_deadline: null,
  grace_period_deadline: null
})

const tmStatusType = (s) => ({ '已注册': 'success', '已续展': 'success', '授权': 'success', '申请中': 'warning', '审中': 'warning', '驳回': 'danger', '已失效': 'danger', '部分授权': 'info' }[s] || '')
const isExpiringSoon = (d) => { if (!d) return false; const diff = new Date(d) - new Date(); return diff > 0 && diff < 365 * 86400000 }
const formatDate = (dt) => { if (!dt) return '—'; return typeof dt === 'string' ? dt.replace('T', ' ').slice(0, 19) : '' }
const actionTagType = (a) => ({ 'create': 'success', 'update': 'warning', 'delete': 'danger', 'login': 'info', 'export': 'info' }[a] || '')
const actionLabel = (a) => ({ 'create': '创建', 'update': '修改', 'delete': '删除', 'login': '登录', 'export': '导出' }[a] || a)

const formatSize = (bytes) => {
  if (!bytes) return '—'
  if (bytes < 1024) return bytes + ' B'
  if (bytes < 1048576) return (bytes / 1024).toFixed(1) + ' KB'
  return (bytes / 1048576).toFixed(1) + ' MB'
}

// Logo URL
const logoUrl = computed(() => {
  if (tm.value.logo_file_id) {
    return `/api/files/${tm.value.logo_file_id}/download?token=${localStorage.getItem('token')}`
  }
  return null
})

// Days calculations
const daysBetween = (d) => {
  if (!d) return 0
  const diff = new Date(d) - new Date()
  return Math.ceil(diff / (1000 * 60 * 60 * 24))
}
const daysUntilValid = computed(() => daysBetween(tm.value.valid_until))
const daysUntilRenewal = computed(() => daysBetween(tm.value.renewal_deadline))
const daysUntilGrace = computed(() => daysBetween(tm.value.grace_period_deadline))

// Renewal timeline events
const renewalEvents = computed(() => {
  const events = []
  if (tm.value.application_date) {
    events.push({ date: tm.value.application_date, title: '商标申请', description: '提交商标注册申请', type: 'primary', hollow: false })
  }
  if (tm.value.registration_date) {
    events.push({ date: tm.value.registration_date, title: '商标注册成功', description: '获得商标注册证', type: 'success', hollow: false })
  }
  if (tm.value.last_renewal_date) {
    events.push({ date: tm.value.last_renewal_date, title: `第${tm.value.renewal_count || 1}次续展`, description: '完成商标续展', type: 'success', hollow: false })
  }
  if (tm.value.renewal_deadline) {
    events.push({ date: tm.value.renewal_deadline, title: '续展截止日', description: '在此日期前需完成续展', type: 'warning', hollow: true })
  }
  if (tm.value.grace_period_deadline) {
    events.push({ date: tm.value.grace_period_deadline, title: '宽展截止日', description: '宽展期最后一天', type: 'danger', hollow: true })
  }
  if (tm.value.valid_until) {
    events.push({ date: tm.value.valid_until, title: '有效期截止', description: '商标保护期结束', type: 'info', hollow: true })
  }
  return events.sort((a, b) => new Date(a.date) - new Date(b.date))
})

const loadData = async () => {
  loading.value = true
  try {
    tm.value = await api.get(`/trademarks/${tmId}`)
  } catch (e) {} finally { loading.value = false }
}

const onLogoUpload = async (response) => {
  // After uploading logo, update the trademark's logo_file_id
  try {
    await api.put(`/trademarks/${tmId}`, { logo_file_id: response.id })
    ElMessage.success('商标图样已更新')
    loadData()
  } catch (e) {
    ElMessage.error('更新图样失败')
  }
}

const openRenewalDialog = () => {
  const today = new Date()
  const valid = tm.value.valid_until ? new Date(tm.value.valid_until) : today
  // New valid date = +10 years from current valid_until
  valid.setFullYear(valid.getFullYear() + 10)
  renewalForm.last_renewal_date = today.toISOString().slice(0, 10)
  renewalForm.valid_until = valid.toISOString().slice(0, 10)
  // Renewal deadline = 6 months before valid_until
  const rd = new Date(valid)
  rd.setMonth(rd.getMonth() - 6)
  renewalForm.renewal_deadline = rd.toISOString().slice(0, 10)
  // Grace period = 6 months after renewal deadline
  const gp = new Date(rd)
  gp.setMonth(gp.getMonth() + 6)
  renewalForm.grace_period_deadline = gp.toISOString().slice(0, 10)
  renewalDialogVisible.value = true
}

const saveRenewal = async () => {
  if (!renewalForm.last_renewal_date || !renewalForm.valid_until) {
    ElMessage.warning('请填写续展日期和新有效期')
    return
  }
  try {
    await api.put(`/trademarks/${tmId}`, {
      last_renewal_date: renewalForm.last_renewal_date,
      valid_until: renewalForm.valid_until,
      renewal_deadline: renewalForm.renewal_deadline,
      grace_period_deadline: renewalForm.grace_period_deadline,
      renewal_count: (tm.value.renewal_count || 0) + 1,
      status: '已续展'
    })
    ElMessage.success('续展登记成功')
    renewalDialogVisible.value = false
    loadData()
  } catch (e) {
    ElMessage.error('续展登记失败')
  }
}

const loadAuditLogs = async () => {
  logsLoading.value = true
  try {
    const res = await api.get('/reports/audit-logs', {
      params: { ...logPage, business_type: 'trademark', business_id: tmId }
    })
    auditLogs.value = res.items
    logPage.total = res.total
  } catch (e) { console.error(e) } finally { logsLoading.value = false }
}

const downloadFile = (fid) => { window.open(`/api/files/${fid}/download?token=${localStorage.getItem('token')}`, '_blank') }
const deleteFile = (fid) => {
  ElMessageBox.confirm('删除此文件？', '确认', { type: 'warning' })
    .then(async () => { await api.delete(`/files/${fid}`); ElMessage.success('已删除'); loadData() }).catch(() => {})
}

watch(activeTab, (tab) => {
  if (tab === 'logs' && auditLogs.value.length === 0) {
    loadAuditLogs()
  }
})

onMounted(loadData)
</script>

<style scoped>
.logo-area { text-align: center; }
.logo-placeholder {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 200px;
  border: 1px dashed #dcdfe6;
  border-radius: 4px;
}
.action-btns { display: flex; gap: 6px; justify-content: center; }
</style>
