<template>
  <div>
    <!-- 说明：本页负责数据的"进出"，统计图表统一放在【数据看板】 -->
    <el-alert type="info" :closable="false" show-icon style="margin-bottom: 16px">
      <template #title>
        <span>本页是<strong>数据导入 / 导出中心</strong>：Excel 批量导入导出、模板下载、导入后数据质量体检。数据可视化与汇报材料（HTML / PDF / PPT）请前往 <strong>数据看板</strong>，操作日志请前往 <strong>系统设置</strong>。</span>
      </template>
    </el-alert>

    <!-- 导出 / 导入 -->
    <el-row :gutter="16" style="margin-bottom: 16px">
      <el-col :span="12">
        <el-card shadow="hover">
          <template #header>
            <div class="card-header"><span>导出 Excel</span><el-icon color="#67C23A"><Download /></el-icon></div>
          </template>
          <div class="btn-grid">
            <el-button v-for="e in exportList" :key="e.cmd" plain @click="handleExport(e.cmd)">
              <el-icon class="btn-ic"><Document /></el-icon>{{ e.label }}
            </el-button>
          </div>
          <div class="tip-text">导出内容与系统内表格字段一致，可直接用于归档或二次加工。</div>
        </el-card>
      </el-col>
      <el-col :span="12">
        <el-card shadow="hover">
          <template #header>
            <div class="card-header"><span>导入 Excel</span><el-icon color="#E6A23C"><Upload /></el-icon></div>
          </template>
          <div class="btn-grid">
            <el-button v-for="i in importList" :key="i.cmd" plain type="warning" @click="handleImport(i.cmd)">
              <el-icon class="btn-ic"><Upload /></el-icon>{{ i.label }}
            </el-button>
          </div>
          <div class="tip-text">导入前请先下载模板；年费/专利导入后系统会自动按规则补齐年费计划。</div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 汇报材料：可按模块选择性导出 + AI 分析 -->
    <el-card shadow="hover" style="margin-bottom: 16px">
      <template #header>
        <div class="card-header">
          <span>汇报材料导出</span>
          <el-button type="success" plain size="small" @click="go('/report-dashboard')">
            <el-icon class="btn-ic"><DataAnalysis /></el-icon>打开数据看板
          </el-button>
        </div>
      </template>

      <div class="rep-opt-row">
        <div class="rep-opt-label">选择导出模块</div>
        <el-checkbox-group v-model="repModules" size="default">
          <el-checkbox v-for="m in moduleOptions" :key="m.value" :value="m.value" :label="m.label" />
        </el-checkbox-group>
      </div>

      <el-checkbox v-model="repAi" style="margin-bottom: 14px">
        <span>
          <el-icon class="ai-ic"><MagicStick /></el-icon>
          附加 <b>AI 智能分析</b>（调用本地大模型，PPT / HTML / PDF 均生效）
        </span>
      </el-checkbox>

      <div class="btn-grid">
        <el-button type="primary" plain :loading="repBusy === 'pdf'" @click="quickExport('pdf')">
          <el-icon class="btn-ic"><Download /></el-icon>导出 PDF
        </el-button>
        <el-button type="warning" plain :loading="repBusy === 'ppt'" @click="quickExport('ppt')">
          <el-icon class="btn-ic"><Tickets /></el-icon>导出 PPT
        </el-button>
        <el-button plain :loading="repBusy === 'html'" @click="quickExport('html')">
          <el-icon class="btn-ic"><Document /></el-icon>导出 HTML
        </el-button>
      </div>
      <div class="tip-text">
        PPT / HTML / PDF 三种格式均按勾选的模块生成对应图表 + 详细数据；勾选「AI 智能分析」时会追加本地大模型生成的解读页。模块全部取消 = 导出全部。
      </div>
    </el-card>

    <!-- 数据质量体检 -->
    <el-card shadow="never" class="dq-card" v-loading="dqLoading">
      <template #header>
        <div class="card-header">
          <div class="dq-title">
            <el-icon :size="20" color="#409EFF"><FirstAidKit /></el-icon>
            <span>数据质量体检</span>
            <el-tag v-if="dq" size="small" effect="plain" type="info">
              共 {{ dq.summary.check_total }} 项检查 · 扫描 {{ dq.summary.scanned_records }} 条记录
            </el-tag>
          </div>
          <div class="dq-actions">
            <span v-if="dq" class="dq-time">体检时间 {{ dq.checked_at }}</span>
            <el-button type="primary" size="small" :icon="Refresh" @click="loadQuality">重新体检</el-button>
          </div>
        </div>
      </template>

      <div v-if="dq" class="dq-body">
        <!-- 左：评分 -->
        <div class="dq-score">
          <el-progress
            type="dashboard"
            :percentage="dq.score"
            :width="150"
            :stroke-width="12"
            :color="scoreColor"
          >
            <template #default>
              <div class="score-inner">
                <div class="score-num" :style="{ color: scoreColor }">{{ dq.score }}</div>
                <div class="score-label">健康度</div>
              </div>
            </template>
          </el-progress>
          <div class="score-verdict" :style="{ color: scoreColor }">{{ scoreVerdict }}</div>
          <div class="score-stats">
            <div class="stat-line"><span class="dot dot-h"></span>严重 <b>{{ dq.summary.high }}</b> 项</div>
            <div class="stat-line"><span class="dot dot-m"></span>一般 <b>{{ dq.summary.medium }}</b> 项</div>
            <div class="stat-line"><span class="dot dot-l"></span>轻微 <b>{{ dq.summary.low }}</b> 项</div>
            <div class="stat-line"><span class="dot dot-p"></span>通过 <b>{{ dq.summary.passed }}</b> 项</div>
          </div>
        </div>

        <!-- 右：问题清单 -->
        <div class="dq-list">
          <el-empty v-if="!dq.issues.length" description="太棒了，全部检查项通过，数据非常干净 🎉" :image-size="90" />
          <el-collapse v-else v-model="activeIssues" accordion>
            <el-collapse-item v-for="it in dq.issues" :key="it.code" :name="it.code">
              <template #title>
                <div class="issue-head">
                  <el-tag :type="sevType(it.severity)" size="small" effect="dark" class="sev-tag">
                    {{ sevLabel(it.severity) }}
                  </el-tag>
                  <span class="issue-cat">{{ it.category }}</span>
                  <span class="issue-title">{{ it.title }}</span>
                  <el-tag :type="sevType(it.severity)" size="small" effect="plain" round>
                    {{ it.count }} 条
                  </el-tag>
                </div>
              </template>
              <div class="issue-hint">{{ it.hint }}</div>
              <div class="issue-samples">
                <div v-for="(s, i) in it.samples" :key="i" class="sample-row">
                  <span class="sample-idx">{{ i + 1 }}</span>
                  <span class="sample-title">{{ s.title }}</span>
                  <span class="sample-sub">{{ s.sub }}</span>
                  <el-button v-if="s.route" type="primary" link size="small" @click="go(s.route)">
                    修复 <el-icon><ArrowRight /></el-icon>
                  </el-button>
                </div>
                <div v-if="it.count > it.samples.length" class="sample-more">
                  还有 {{ it.count - it.samples.length }} 条未展示
                </div>
              </div>
              <div class="issue-foot">
                <el-button size="small" type="primary" plain :icon="Position" @click="go(it.route)">
                  前往 {{ it.category }}模块 批量处理
                </el-button>
              </div>
            </el-collapse-item>
          </el-collapse>

          <!-- 已通过 -->
          <div v-if="dq.passed.length" class="passed-box">
            <div class="passed-head" @click="showPassed = !showPassed">
              <el-icon color="#67C23A"><CircleCheck /></el-icon>
              已通过 {{ dq.passed.length }} 项检查
              <el-icon class="passed-arrow" :class="{ open: showPassed }"><ArrowRight /></el-icon>
            </div>
            <div v-show="showPassed" class="passed-tags">
              <el-tag v-for="p in dq.passed" :key="p.code" size="small" type="success" effect="plain">
                {{ p.category }} · {{ p.title }}
              </el-tag>
            </div>
          </div>
        </div>
      </div>
      <div class="tip-text">体检规则覆盖专利、商标、年费、奖金、基础档案五大类共 26 项，建议每次 Excel 批量导入后执行一次。</div>
    </el-card>

    <!-- Import dialog -->
    <el-dialog v-model="importDialog.visible" :title="importDialog.title" width="500px">
      <div style="margin-bottom: 16px">
        <el-button type="primary" link @click="downloadTemplate(importDialog.type)">下载模板</el-button>
      </div>
      <el-upload
        :show-file-list="true"
        :limit="1"
        :accept="acceptType"
        :http-request="handleImportUpload"
      >
        <el-button type="primary">选择文件</el-button>
      </el-upload>
      <div v-if="importDialog.result" style="margin-top: 16px">
        <el-alert :title="importDialog.result.message" :type="importDialog.result.failed > 0 ? 'warning' : 'success'" :closable="false" />
      </div>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import {
  Download, Upload, Document, DataAnalysis, Tickets,
  FirstAidKit, Refresh, ArrowRight, Position, CircleCheck, MagicStick
} from '@element-plus/icons-vue'
import api from '@/api'

const router = useRouter()

// 固定扩展名（避免 Vue 解析以点开头的字符串报错）
const acceptType = '.xlsx,.xls'

const exportList = [
  { cmd: 'patents', label: '专利清单' },
  { cmd: 'trademarks', label: '商标清单' },
  { cmd: 'fees', label: '专利年费' },
  { cmd: 'fee-standards', label: '费用标准' }
]

const importList = [
  { cmd: 'patent', label: '导入专利' },
  { cmd: 'trademark', label: '导入商标' },
  { cmd: 'fee', label: '导入年费' },
  { cmd: 'old-bonus', label: '导入旧规则奖金' }
]

// Export
const handleExport = (command) => {
  const token = localStorage.getItem('token')
  window.open(`/api/io/export/${command}?token=${token}`, '_blank')
}

// 汇报材料导出（后端生成，支持按模块选择 + AI 分析）
const moduleOptions = [
  { value: 'overview', label: '核心概览' },
  { value: 'patent', label: '专利与商标' },
  { value: 'bonus', label: '专利奖金' },
  { value: 'fee', label: '年费管理' },
  { value: 'system', label: '系统能力' }
]
const repModules = ref(['overview', 'patent', 'bonus', 'fee', 'system'])
const repAi = ref(false)
const repBusy = ref('')

const quickExport = async (type) => {
  repBusy.value = type
  try {
    const token = localStorage.getItem('token')
    const params = new URLSearchParams()
    params.set('token', token)
    // 未选任何模块 = 全部（后端空串即全量）
    if (repModules.value.length && repModules.value.length < moduleOptions.length) {
      params.set('modules', repModules.value.join(','))
    }
    if (repAi.value) params.set('ai', 'true')
    const res = await fetch(`/api/export/dashboard/${type}?${params.toString()}`)
    if (!res.ok) throw new Error('导出失败')
    const blob = await res.blob()
    const ext = type === 'html' ? 'html' : type
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `IP资产汇报_${new Date().getFullYear()}年.${ext}`
    document.body.appendChild(a)
    a.click()
    a.remove()
    URL.revokeObjectURL(url)
    ElMessage.success('导出成功，请查看下载')
    if (repAi.value) ElMessage.info('已附加 AI 智能分析（本地大模型生成）')
  } catch (e) {
    console.error(e)
    ElMessage.error('导出失败')
  } finally {
    repBusy.value = ''
  }
}

const go = (path) => router.push(path)

// Import
const importDialog = reactive({
  visible: false,
  title: '',
  type: '',
  result: null
})

const handleImport = (command) => {
  const titles = {
    patent: '导入专利',
    trademark: '导入商标',
    fee: '导入年费',
    'old-bonus': '导入旧规则奖金'
  }
  importDialog.title = titles[command] || '导入'
  importDialog.type = command
  importDialog.result = null
  importDialog.visible = true
}

const handleImportUpload = async ({ file }) => {
  const formData = new FormData()
  formData.append('file', file)
  try {
    const endpoint = importDialog.type === 'old-bonus' ? '/io/import/old-bonus' : `/io/import/${importDialog.type}s`
    const res = await api.post(endpoint, formData, {
      headers: { 'Content-Type': 'multipart/form-data' }
    })
    importDialog.result = res
    ElMessage.success(res.message || '导入完成')
  } catch (e) {
    ElMessage.error('导入失败')
    console.error(e)
  }
}

const downloadTemplate = (type) => {
  const token = localStorage.getItem('token')
  window.open(`/api/io/template/${type}?token=${token}`, '_blank')
}

// ---- 数据质量体检 ----
const dq = ref(null)
const dqLoading = ref(false)
const activeIssues = ref('')
const showPassed = ref(false)

const SEV = {
  high: { label: '严重', type: 'danger' },
  medium: { label: '一般', type: 'warning' },
  low: { label: '轻微', type: 'info' }
}
const sevLabel = (s) => (SEV[s] || SEV.low).label
const sevType = (s) => (SEV[s] || SEV.low).type

const scoreColor = computed(() => {
  const s = dq.value?.score ?? 0
  if (s >= 90) return '#67C23A'
  if (s >= 75) return '#409EFF'
  if (s >= 60) return '#E6A23C'
  return '#F56C6C'
})

const scoreVerdict = computed(() => {
  const s = dq.value?.score ?? 0
  if (s >= 90) return '数据非常健康'
  if (s >= 75) return '数据基本健康'
  if (s >= 60) return '存在待补齐项'
  return '建议尽快清理'
})

const loadQuality = async () => {
  dqLoading.value = true
  try {
    const res = await api.get('/reports/data-quality', { params: { sample: 5 } })
    dq.value = res
    activeIssues.value = res.issues?.[0]?.code || ''
  } catch (e) {
    console.error(e)
    ElMessage.error('体检失败')
  } finally {
    dqLoading.value = false
  }
}

onMounted(() => loadQuality())
</script>

<style scoped>
.card-header { display: flex; justify-content: space-between; align-items: center; }
.btn-grid { display: flex; flex-wrap: wrap; gap: 10px; }
.btn-ic { margin-right: 5px; vertical-align: -2px; }
.tip-text { margin-top: 12px; font-size: 12px; color: #909399; line-height: 1.6; }
.rep-opt-row { display: flex; align-items: center; gap: 14px; flex-wrap: wrap; margin-bottom: 10px; }
.rep-opt-label { font-size: 13px; color: #606266; font-weight: 600; }
.rep-opt-row .el-checkbox-group { gap: 6px 14px; flex-wrap: wrap; }
.ai-ic { margin-right: 3px; vertical-align: -2px; color: #409EFF; }

/* ===== 数据质量体检 ===== */
.dq-card :deep(.el-card__header) {
  background: linear-gradient(135deg, #f5f9ff 0%, #fafbfc 100%);
}
.dq-title { display: flex; align-items: center; gap: 8px; font-weight: 600; }
.dq-actions { display: flex; align-items: center; gap: 12px; }
.dq-time { font-size: 12px; color: #909399; }

.dq-body { display: flex; gap: 24px; align-items: flex-start; }

/* 评分区 */
.dq-score {
  flex-shrink: 0;
  width: 200px;
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 8px 0 4px;
  border-right: 1px solid #f0f2f5;
}
.score-inner { line-height: 1.2; }
.score-num { font-size: 34px; font-weight: 700; }
.score-label { font-size: 12px; color: #909399; margin-top: 2px; }
.score-verdict { margin-top: 10px; font-size: 14px; font-weight: 600; }
.score-stats { margin-top: 16px; width: 100%; padding: 0 18px; }
.stat-line {
  display: flex; align-items: center; gap: 6px;
  font-size: 13px; color: #606266; padding: 4px 0;
}
.stat-line b { margin-left: auto; color: #303133; }
.dot { width: 8px; height: 8px; border-radius: 50%; flex-shrink: 0; }
.dot-h { background: #F56C6C; }
.dot-m { background: #E6A23C; }
.dot-l { background: #909399; }
.dot-p { background: #67C23A; }

/* 问题清单 */
.dq-list { flex: 1; min-width: 0; }
.dq-list :deep(.el-collapse) { border-top: none; }
.dq-list :deep(.el-collapse-item__header) { border-bottom: 1px solid #f0f2f5; height: 46px; }
.dq-list :deep(.el-collapse-item__wrap) { border-bottom: 1px solid #f0f2f5; }

.issue-head { display: flex; align-items: center; gap: 10px; width: 100%; padding-right: 8px; }
.sev-tag { flex-shrink: 0; width: 44px; text-align: center; }
.issue-cat {
  flex-shrink: 0; font-size: 12px; color: #909399;
  background: #f4f4f5; padding: 2px 8px; border-radius: 4px;
}
.issue-title {
  flex: 1; min-width: 0; font-size: 14px; color: #303133;
  overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
}

.issue-hint {
  font-size: 12px; color: #909399; line-height: 1.7;
  background: #fafafa; border-left: 3px solid #dcdfe6;
  padding: 8px 12px; border-radius: 0 4px 4px 0; margin-bottom: 10px;
}
.issue-samples { }
.sample-row {
  display: flex; align-items: center; gap: 10px;
  padding: 7px 4px; font-size: 13px;
  border-bottom: 1px dashed #f0f2f5;
}
.sample-row:hover { background: #fafcff; }
.sample-idx {
  flex-shrink: 0; width: 18px; height: 18px; line-height: 18px;
  text-align: center; font-size: 11px; color: #909399;
  background: #f4f4f5; border-radius: 50%;
}
.sample-title {
  flex: 1; min-width: 0; color: #303133;
  overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
}
.sample-sub { flex-shrink: 0; font-size: 12px; color: #909399; }
.sample-more { padding: 8px 4px; font-size: 12px; color: #C0C4CC; }
.issue-foot { margin-top: 12px; }

/* 已通过 */
.passed-box { margin-top: 16px; }
.passed-head {
  display: flex; align-items: center; gap: 6px;
  font-size: 13px; color: #67C23A; cursor: pointer;
  user-select: none; padding: 6px 0;
}
.passed-arrow { transition: transform 0.25s cubic-bezier(0.16, 1, 0.3, 1); }
.passed-arrow.open { transform: rotate(90deg); }
.passed-tags { display: flex; flex-wrap: wrap; gap: 6px; margin-top: 8px; }

@media (max-width: 1100px) {
  .dq-body { flex-direction: column; }
  .dq-score { width: 100%; border-right: none; border-bottom: 1px solid #f0f2f5; padding-bottom: 16px; }
  .score-stats { display: flex; gap: 20px; justify-content: center; }
  .stat-line b { margin-left: 4px; }
}
</style>
