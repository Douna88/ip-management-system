<template>
  <div>
    <el-card>
      <template #header>
        <div class="card-header">
          <span>商标注册范围库</span>
          <div>
            <el-button type="success" :icon="Download" @click="exportData">导出Excel</el-button>
            <el-button type="primary" :icon="Plus" @click="showDialog()">添加范围</el-button>
          </div>
        </div>
      </template>

      <el-alert type="info" :closable="false" style="margin-bottom: 16px">
        注册范围库完整呈现各业务线商标注册的尼斯分类、细分小类、小类名称及具体产品/服务信息。数据来源：Trademark list.xlsx。
      </el-alert>

      <!-- Group tabs -->
      <el-tabs v-model="activeGroup" @tab-change="onGroupChange">
        <el-tab-pane v-for="group in groupNames" :key="group" :label="`${group} (${(groupedScopes[group] || []).length})`" :name="group" />
      </el-tabs>

      <!-- Data table for selected group -->
      <el-table :data="currentGroupData" border stripe size="small" style="width: 100%">
        <el-table-column type="index" label="#" width="50" align="center" />
        <el-table-column prop="nice_class" label="类别" width="80" align="center">
          <template #default="{ row }">
            <el-tag :color="classColor(row.nice_class)" effect="dark" size="small" style="border:none;color:#fff">第{{ row.nice_class }}类</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="subclass_code" label="细分小类" width="100" align="center">
          <template #default="{ row }">
            <span style="font-family: 'Courier New', monospace; font-weight: 600">{{ row.subclass_code || '—' }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="subclass_name" label="小类名称" min-width="280" show-overflow-tooltip>
          <template #default="{ row }">{{ row.subclass_name || '—' }}</template>
        </el-table-column>
        <el-table-column prop="specific_products" label="具体产品（服务）" min-width="350" show-overflow-tooltip>
          <template #default="{ row }">
            <span v-if="row.specific_products && row.specific_products !== '/'">{{ row.specific_products }}</span>
            <span v-else style="color: #c0c4cc">/</span>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="120" fixed="right" align="center">
          <template #default="{ row }">
            <div class="action-btns">
              <el-tooltip content="编辑" placement="top">
                <el-button circle size="small" type="warning" plain @click="showDialog(row)">
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

      <!-- Summary cards -->
      <el-row :gutter="16" style="margin-top: 20px">
        <el-col v-for="group in groupNames" :key="group" :span="24 / groupNames.length">
          <el-card shadow="hover" class="summary-card">
            <el-statistic :title="group" :value="getGroupStats(group).total" suffix="条" />
            <div style="margin-top: 8px">
              <el-tag v-for="cls in getGroupStats(group).classes" :key="cls" :color="classColor(cls)" effect="dark" size="small" style="margin-right: 6px; margin-bottom: 4px; border:none; color:#fff">
                第{{ cls }}类
              </el-tag>
            </div>
          </el-card>
        </el-col>
      </el-row>
    </el-card>

    <!-- Add/Edit Dialog -->
    <el-dialog v-model="dialogVisible" :title="editing.id ? '编辑范围' : '添加范围'" width="600px">
      <el-form :model="editing" label-width="100px">
        <el-form-item label="范围组">
          <el-select v-model="editing.scope_group" style="width: 100%">
            <el-option label="运动台" value="运动台" />
            <el-option label="光学传感" value="光学传感" />
            <el-option label="电子" value="电子" />
            <el-option label="其他" value="其他" />
          </el-select>
        </el-form-item>
        <el-form-item label="尼斯分类号">
          <el-input-number v-model="editing.nice_class" :min="1" :max="45" style="width: 100%" />
        </el-form-item>
        <el-form-item label="细分小类">
          <el-input v-model="editing.subclass_code" placeholder="如：0705" />
        </el-form-item>
        <el-form-item label="小类名称">
          <el-input v-model="editing.subclass_name" type="textarea" :rows="2" placeholder="如：印刷工业用机械及器具" />
        </el-form-item>
        <el-form-item label="类别名称">
          <el-input v-model="editing.class_name" placeholder="如：机械设备" />
        </el-form-item>
        <el-form-item label="具体产品">
          <el-input v-model="editing.specific_products" type="textarea" :rows="3" placeholder="该小类下包含的具体产品/服务说明" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" @click="handleSave">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus, Download, Edit, Delete } from '@element-plus/icons-vue'
import api from '@/api'

const scopes = ref([])
const activeGroup = ref('运动台')
const dialogVisible = ref(false)
const editing = reactive({
  id: null, scope_group: '运动台', nice_class: 9, subclass_code: '',
  subclass_name: '', class_name: '', specific_products: ''
})

const groupedScopes = computed(() => {
  const groups = {}
  for (const s of scopes.value) {
    if (!groups[s.scope_group]) groups[s.scope_group] = []
    groups[s.scope_group].push(s)
  }
  return groups
})

const groupNames = computed(() => {
  return Object.keys(groupedScopes.value).sort()
})

const currentGroupData = computed(() => {
  return groupedScopes.value[activeGroup.value] || []
})

const getGroupStats = (group) => {
  const items = groupedScopes.value[group] || []
  const classSet = new Set()
  for (const item of items) {
    classSet.add(item.nice_class)
  }
  return { total: items.length, classes: [...classSet].sort((a, b) => a - b) }
}

const onGroupChange = (name) => {
  activeGroup.value = name
}

// Color palette for different nice_class values — each class gets a distinct color
const CLASS_COLORS = [
  '#409EFF', '#67C23A', '#E6A23C', '#F56C6C', '#909399',
  '#9B59B6', '#1ABC9C', '#3498DB', '#E74C3C', '#2ECC71',
  '#F39C12', '#8E44AD', '#16A085', '#D35400', '#C0392B',
  '#2980B9', '#27AE60', '#D4AC0D', '#7D3C98', '#117A65'
]
const classColor = (niceClass) => {
  const idx = (Number(niceClass) - 1) % CLASS_COLORS.length
  return CLASS_COLORS[idx >= 0 ? idx : 0]
}

const loadData = async () => {
  try {
    const res = await api.get('/trademark-scopes')
    scopes.value = res.items || []
    // Auto-select first group if current is empty
    if (currentGroupData.value.length === 0 && groupNames.value.length > 0) {
      activeGroup.value = groupNames.value[0]
    }
  } catch (e) { console.error(e) }
}

const showDialog = (item) => {
  if (item) {
    Object.assign(editing, item)
  } else {
    Object.assign(editing, {
      id: null, scope_group: activeGroup.value, nice_class: 9, subclass_code: '',
      subclass_name: '', class_name: '', specific_products: ''
    })
  }
  dialogVisible.value = true
}

const handleSave = async () => {
  if (!editing.class_name && !editing.subclass_name) {
    ElMessage.warning('请至少填写类别名称或小类名称')
    return
  }
  try {
    if (editing.id) {
      await api.put(`/trademark-scopes/${editing.id}`, editing)
    } else {
      await api.post('/trademark-scopes', editing)
    }
    ElMessage.success('保存成功')
    dialogVisible.value = false
    loadData()
  } catch (e) { console.error(e) }
}

const handleDelete = async (item) => {
  try {
    await ElMessageBox.confirm(`确认删除"第${item.nice_class}类 ${item.subclass_code || ''}"？`, '提示', { type: 'warning' })
    await api.delete(`/trademark-scopes/${item.id}`)
    ElMessage.success('已删除')
    loadData()
  } catch (e) { if (e !== 'cancel') console.error(e) }
}

const exportData = () => {
  // Export all scope data as CSV
  const rows = []
  rows.push(['范围组', '类别', '细分小类', '小类名称', '具体产品（服务）'])
  for (const s of scopes.value) {
    rows.push([
      s.scope_group || '',
      String(s.nice_class || ''),
      s.subclass_code || '',
      s.subclass_name || '',
      s.specific_products || ''
    ])
  }
  const csv = rows.map(r => r.map(c => `"${c}"`).join(',')).join('\n')
  const blob = new Blob(['\ufeff' + csv], { type: 'text/csv;charset=utf-8;' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = '商标注册范围库.csv'
  a.click()
  URL.revokeObjectURL(url)
  ElMessage.success('导出成功')
}

onMounted(() => loadData())
</script>

<style scoped>
.card-header { display: flex; justify-content: space-between; align-items: center; }
.summary-card { text-align: center; }
.action-btns { display: flex; gap: 6px; justify-content: center; }
</style>
