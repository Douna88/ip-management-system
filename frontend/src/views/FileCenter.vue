<template>
  <div>
    <el-card>
      <template #header>
        <div class="card-header">
          <span>文件中心</span>
          <div class="upload-area">
            <el-select v-model="uploadBizType" placeholder="归属模块(可选)" clearable size="default" style="width: 150px">
              <el-option label="专利" value="patent" />
              <el-option label="商标" value="trademark" />
              <el-option label="代理机构" value="agency" />
              <el-option label="奖金" value="bonus" />
              <el-option label="费用标准" value="standard" />
            </el-select>
            <el-upload :show-file-list="false" :multiple="true" :http-request="handleUpload" :before-upload="beforeUpload">
              <el-button type="primary" :icon="Upload" :loading="uploading" :disabled="uploading">
                {{ uploading ? `上传中 ${uploadDone}/${uploadTotal}` : '批量上传' }}
              </el-button>
            </el-upload>
          </div>
        </div>
      </template>

      <el-form :inline="true" :model="filters" class="filter-bar">
        <el-form-item>
          <el-input v-model="filters.search" placeholder="搜索文件名" clearable @keyup.enter="loadData" style="width: 200px" />
        </el-form-item>
        <el-form-item>
          <el-select v-model="filters.file_type" placeholder="文件类型" clearable @change="loadData" style="width: 120px">
            <el-option label="PDF" value="pdf" />
            <el-option label="Word" value="word" />
            <el-option label="Excel" value="excel" />
            <el-option label="图片" value="image" />
            <el-option label="其他" value="other" />
          </el-select>
        </el-form-item>
        <el-form-item>
          <el-select v-model="filters.business_type" placeholder="业务模块" clearable @change="loadData" style="width: 140px">
            <el-option label="专利" value="patent" />
            <el-option label="商标" value="trademark" />
            <el-option label="代理机构" value="agency" />
            <el-option label="奖金" value="bonus" />
            <el-option label="费用标准" value="standard" />
          </el-select>
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="loadData">查询</el-button>
        </el-form-item>
      </el-form>

      <el-table :data="files" v-loading="loading" stripe @row-click="handleRowClick" style="cursor: pointer">
        <el-table-column label="文件名" prop="original_name" min-width="200" show-overflow-tooltip>
          <template #default="{ row }">
            <el-icon :size="16" style="vertical-align: middle; margin-right: 4px">
              <Document />
            </el-icon>
            {{ row.original_name }}
          </template>
        </el-table-column>
        <el-table-column label="类型" prop="file_type" width="80">
          <template #default="{ row }">
            <el-tag :type="getTypeTag(row.file_type)" size="small">{{ row.file_type }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="大小" width="100">
          <template #default="{ row }">{{ formatSize(row.file_size) }}</template>
        </el-table-column>
        <el-table-column label="业务模块" prop="business_type" width="100">
          <template #default="{ row }">
            <el-tag v-if="row.business_type" size="small" effect="plain">{{ businessTypeLabel(row.business_type) }}</el-tag>
            <span v-else>—</span>
          </template>
        </el-table-column>
        <el-table-column label="上传时间" prop="uploaded_at" width="160">
          <template #default="{ row }">{{ formatDate(row.uploaded_at) }}</template>
        </el-table-column>
        <el-table-column label="操作" width="140" align="center">
          <template #default="{ row }">
            <div class="action-btns">
              <el-tooltip content="下载" placement="top">
                <el-button circle size="small" type="primary" plain @click.stop="handleDownload(row)">
                  <el-icon><Download /></el-icon>
                </el-button>
              </el-tooltip>
              <el-tooltip content="删除" placement="top">
                <el-button circle size="small" type="danger" plain @click.stop="handleDelete(row)">
                  <el-icon><Delete /></el-icon>
                </el-button>
              </el-tooltip>
            </div>
          </template>
        </el-table-column>
      </el-table>

      <div class="pagination-bar">
        <el-pagination
          v-model:current-page="page"
          v-model:page-size="pageSize"
          :total="total"
          :page-sizes="[20, 50, 100]"
          layout="total, sizes, prev, pager, next"
          @size-change="loadData"
          @current-change="loadData"
        />
      </div>
    </el-card>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Document, Upload, Download, Delete } from '@element-plus/icons-vue'
import api from '@/api'

const loading = ref(false)
const files = ref([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)
const filters = reactive({ search: '', file_type: '', business_type: '' })
const uploadBizType = ref('')
const uploading = ref(false)
const uploadTotal = ref(0)
const uploadDone = ref(0)

const loadData = async () => {
  loading.value = true
  try {
    const res = await api.get('/files', {
      params: {
        search: filters.search,
        file_type: filters.file_type,
        business_type: filters.business_type,
        page: page.value,
        page_size: pageSize.value
      }
    })
    files.value = res.items || []
    total.value = res.total || 0
  } catch (e) {
    console.error(e)
  } finally {
    loading.value = false
  }
}

const getTypeTag = (type) => {
  const map = { pdf: 'danger', word: 'primary', excel: 'success', image: 'warning', other: 'info' }
  return map[type] || 'info'
}

const formatSize = (bytes) => {
  if (!bytes) return '—'
  if (bytes < 1024) return bytes + ' B'
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB'
  return (bytes / 1024 / 1024).toFixed(1) + ' MB'
}

const formatDate = (dt) => {
  if (!dt) return '—'
  return new Date(dt).toLocaleString('zh-CN')
}

const businessTypeLabel = (t) => {
  const map = { patent: '专利', trademark: '商标', agency: '代理机构', bonus: '奖金', standard: '费用标准' }
  return map[t] || t
}

const beforeUpload = (file) => {
  const maxSize = 100 * 1024 * 1024
  if (file.size > maxSize) {
    ElMessage.error(`"${file.name}" 超过100MB限制，已跳过`)
    return false
  }
  // before-upload 对每个文件各触发一次，累加即本批总数
  uploadTotal.value++
  uploading.value = true
  return true
}

const handleUpload = async ({ file }) => {
  const formData = new FormData()
  formData.append('file', file)
  try {
    await api.post('/files/upload', formData, {
      params: { business_type: uploadBizType.value || '' },
      headers: { 'Content-Type': 'multipart/form-data' }
    })
    uploadDone.value++
    loadData()
  } catch (e) {
    console.error(e)
    ElMessage.error(`"${file.name}" 上传失败`)
  } finally {
    if (uploadDone.value >= uploadTotal.value) {
      ElMessage.success(`本批上传完成：${uploadDone.value}/${uploadTotal.value}`)
      uploading.value = false
      uploadTotal.value = 0
      uploadDone.value = 0
    }
  }
}

const handleDownload = (row) => {
  window.open(`/api/files/${row.id}/download?token=${localStorage.getItem('token')}`, '_blank')
}

const handleDelete = async (row) => {
  try {
    await ElMessageBox.confirm(`确认删除文件"${row.original_name}"？`, '提示', { type: 'warning' })
    await api.delete(`/files/${row.id}`)
    ElMessage.success('已删除')
    loadData()
  } catch (e) {
    if (e !== 'cancel') console.error(e)
  }
}

const handleRowClick = (row) => {
  handleDownload(row)
}

onMounted(() => loadData())
</script>

<style scoped>
.card-header { display: flex; justify-content: space-between; align-items: center; }
.filter-bar { margin-bottom: 16px; }
.pagination-bar { margin-top: 16px; display: flex; justify-content: flex-end; }
.action-btns { display: flex; gap: 6px; justify-content: center; }
</style>
