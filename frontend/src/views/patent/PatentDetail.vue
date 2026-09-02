<template>
  <div v-loading="loading">
    <el-page-header @back="$router.back()" style="margin-bottom:16px">
      <template #content><span style="font-size:16px">{{ patent.patent_name || '专利详情' }}</span></template>
    </el-page-header>

    <el-tabs v-model="activeTab">
      <!-- Basic Info -->
      <el-tab-pane label="基本信息" name="info">
        <el-card shadow="never">
          <el-descriptions :column="3" border>
            <el-descriptions-item label="申请号">{{ patent.application_no }}</el-descriptions-item>
            <el-descriptions-item label="专利名称">{{ patent.patent_name }}</el-descriptions-item>
            <el-descriptions-item label="类型"><el-tag :type="typeTagType(patent.patent_type)" size="small">{{ patent.patent_type }}</el-tag></el-descriptions-item>
            <el-descriptions-item label="状态"><el-tag :type="statusTagType(patent.status)" size="small">{{ patent.status }}</el-tag></el-descriptions-item>
            <el-descriptions-item label="申请日">{{ patent.application_date || '—' }}</el-descriptions-item>
            <el-descriptions-item label="授权号">{{ patent.authorization_no || '—' }}</el-descriptions-item>
            <el-descriptions-item label="授权日">{{ patent.authorization_date || '—' }}</el-descriptions-item>
            <el-descriptions-item label="权利人">{{ patent.applicant || '—' }}</el-descriptions-item>
            <el-descriptions-item label="发明人">{{ patent.inventors || '—' }}</el-descriptions-item>
            <el-descriptions-item label="IPC分类号">{{ patent.ipc_classification || '—' }}</el-descriptions-item>
            <el-descriptions-item label="对应项目">{{ patent.correspondence_project || '—' }}</el-descriptions-item>
            <el-descriptions-item label="对应产品">{{ patent.correspondence_product || '—' }}</el-descriptions-item>
            <el-descriptions-item label="代理机构">{{ patent.agency_name || '—' }}</el-descriptions-item>
            <el-descriptions-item label="代理案件号">{{ patent.agency_case_no || '—' }}</el-descriptions-item>
            <el-descriptions-item label="PCT"><el-tag v-if="patent.is_pct" type="danger" size="small">是</el-tag><span v-else>否</span></el-descriptions-item>
            <el-descriptions-item label="快速预审"><el-tag v-if="patent.quick_examination" type="success" size="small">是</el-tag><span v-else>否</span></el-descriptions-item>
            <el-descriptions-item label="优审"><el-tag v-if="patent.expedited_examination" type="warning" size="small">是</el-tag><span v-else>否</span></el-descriptions-item>
            <el-descriptions-item label="费减"><el-tag v-if="patent.fee_reduction" type="warning" size="small">{{ patent.fee_reduction_rate || '是' }}</el-tag><span v-else>否</span></el-descriptions-item>
            <el-descriptions-item label="官费">¥{{ patent.official_fee || 0 }}</el-descriptions-item>
            <el-descriptions-item label="代理费">¥{{ patent.agency_fee || 0 }}</el-descriptions-item>
            <el-descriptions-item label="预审费">¥{{ patent.pre_examination_fee || 0 }}</el-descriptions-item>
            <el-descriptions-item label="保护要素" :span="3">{{ patent.protection_element || '—' }}</el-descriptions-item>
          </el-descriptions>
        </el-card>
      </el-tab-pane>

      <!-- Patent Fees with Curve Chart -->
      <el-tab-pane label="年费记录" name="fees">
        <!-- Official website links -->
        <el-card shadow="never" style="margin-bottom: 16px">
          <template #header>
            <div style="display: flex; justify-content: space-between; align-items: center">
              <span>官方查询入口</span>
              <el-tag size="small" type="info">快捷跳转</el-tag>
            </div>
          </template>
          <div class="official-links">
            <el-button type="primary" size="small" @click="openExternal('https://pss-system.cponline.cnipa.gov.cn/conventionalSearch')">国知局专利查询</el-button>
            <el-button type="success" size="small" @click="openExternal('https://cponline.cnipa.gov.cn')">国知局专利业务办理</el-button>
            <el-button type="warning" size="small" @click="openExternal('https://pss-system.cponline.cnipa.gov.cn/conventionalSearch')">专利检索系统</el-button>
            <el-button type="info" size="small" @click="openExternal('https://cponline.cnipa.gov.cn/FeeReduction')">专利费减备案</el-button>
            <el-button size="small" @click="openExternal('https://www.cnipa.gov.cn/')">国知局官网</el-button>
          </div>
        </el-card>

        <!-- Fee Completeness Audit -->
        <el-card shadow="never" style="margin-bottom: 16px; border-left: 3px solid var(--el-color-info)" v-if="feeAudit && feeAudit.has_fee_rule">
          <template #header>
            <div style="display: flex; justify-content: space-between; align-items: center">
              <span>年费完整性审核 <span style="font-size: 12px; color: #909399; margin-left: 6px">按 {{ patent.patent_type }} 应有 {{ feeAudit.expected_count }} 年 / 实有 {{ feeAudit.existing_count }} 年</span></span>
              <el-tag :type="feeAuditTagType" size="small">{{ feeAuditSummary }}</el-tag>
            </div>
          </template>
          <div v-if="feeAudit.complete" style="color: #67c23a; font-size: 13px">
            ✓ 年费记录完整，各年度均已建立记录。
          </div>
          <div v-else>
            <div style="font-size: 13px; line-height: 2">
              <div v-if="overdueFees.length">
                <el-tag type="danger" size="small" style="margin-right: 6px">已过期未写</el-tag>
                <span style="color: #f56c6c">{{ fmtYearList(overdueFees) }}</span>
                <span style="color: #909399; margin-left: 8px">应缴日已过但库内无记录，请尽快核实是否漏缴</span>
              </div>
              <div v-if="futureFees.length">
                <el-tag size="small" type="info" style="margin-right: 6px">未来年份</el-tag>
                <span>{{ fmtYearList(futureFees) }}</span>
                <span style="color: #909399; margin-left: 8px">应缴日未到，尚未产生记录属正常</span>
              </div>
              <div v-if="feeAudit.duplicate_years.length">
                <el-tag type="warning" size="small" style="margin-right: 6px">重复记录</el-tag>
                <span style="color: #e6a23c">第 {{ feeAudit.duplicate_years.join('、第') }} 年存在多条年费记录，请核对</span>
              </div>
            </div>
            <div v-if="feeAudit.missing.length" style="margin-top: 10px">
              <el-button type="warning" size="small" :loading="completingFees" @click="completeFees">
                一键补写 {{ feeAudit.missing.length }} 个缺失年份
              </el-button>
              <span style="font-size: 12px; color: #c0c4cc; margin-left: 8px">只新增缺失年份的「待缴」记录，已有记录与凭证不受影响</span>
            </div>
          </div>
        </el-card>

        <!-- Fee Curve Chart -->
        <el-card shadow="never" style="margin-bottom: 16px" v-if="(patent.fees || []).length > 0">
          <template #header>年费缴纳曲线</template>
          <v-chart :option="feeCurveOption" style="height: 300px" autoresize />
        </el-card>

        <el-card shadow="never">
          <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px">
            <el-button type="primary" size="small" @click="openFeeDialog">添加年费记录</el-button>
            <el-upload
              :show-file-list="false"
              :before-upload="beforeFeeFileUpload"
              accept=".doc,.docx,.xls,.xlsx,.pdf"
            >
              <el-button type="success" size="small" :icon="UploadFilled">上传年费缴纳凭证</el-button>
              <template #tip><span style="font-size:12px;color:#909399;margin-left:8px">支持 Word/Excel/PDF</span></template>
            </el-upload>
          </div>
          <el-table :data="patent.fees || []" border stripe size="small">
            <el-table-column prop="fee_year" label="年度" width="70" />
            <el-table-column prop="due_date" label="应缴日" width="110" />
            <el-table-column prop="actual_pay_date" label="实缴日" width="110" />
            <el-table-column prop="standard_amount" label="标准金额" width="100"><template #default="{row}">¥{{ row.standard_amount || 0 }}</template></el-table-column>
            <el-table-column prop="reduced_amount" label="费减金额" width="100"><template #default="{row}">¥{{ row.reduced_amount || 0 }}</template></el-table-column>
            <el-table-column prop="actual_pay_amount" label="实付金额" width="100"><template #default="{row}">¥{{ row.actual_pay_amount || 0 }}</template></el-table-column>
            <el-table-column prop="status" label="状态" width="80"><template #default="{row}"><el-tag :type="row.status==='已缴'?'success':'warning'" size="small">{{ row.status }}</el-tag></template></el-table-column>
            <el-table-column prop="receipt_no" label="收据号" width="120" />
            <el-table-column label="凭证文件" width="100" align="center">
              <template #default="{row}">
                <el-button v-if="row.receipt_file_id" text type="primary" size="small" @click="downloadFeeFile(row.receipt_file_id)">查看</el-button>
                <el-upload
                  v-else
                  :show-file-list="false"
                  :before-upload="(file) => beforeFeeRecordFileUpload(file, row)"
                  accept=".doc,.docx,.xls,.xlsx,.pdf"
                >
                  <el-button text type="success" size="small">上传</el-button>
                </el-upload>
              </template>
            </el-table-column>
            <el-table-column label="操作" width="120" align="center">
              <template #default="{row}">
                <div class="action-btns">
                  <el-tooltip content="编辑年费" placement="top">
                    <el-button circle size="small" type="warning" plain @click="editFee(row)">
                      <el-icon><EditPen /></el-icon>
                    </el-button>
                  </el-tooltip>
                  <el-tooltip content="删除年费" placement="top">
                    <el-button circle size="small" type="danger" plain @click="deleteFee(row)">
                      <el-icon><Delete /></el-icon>
                    </el-button>
                  </el-tooltip>
                </div>
              </template>
            </el-table-column>
          </el-table>
        </el-card>
      </el-tab-pane>

      <!-- Bonus Association -->
      <el-tab-pane label="奖金关联" name="bonus">
        <el-card shadow="never">
          <template #header>
            <div style="display: flex; justify-content: space-between; align-items: center">
              <span>奖金记录</span>
              <el-tag v-if="bonusData.item_count > 0" type="success" size="small">
                共 {{ bonusData.item_count }} 条记录，累计 ¥{{ bonusData.total_amount?.toFixed(2) }}
              </el-tag>
            </div>
          </template>
          <el-empty v-if="bonusData.item_count === 0" description="暂无奖金记录" />
          <el-table v-else :data="bonusData.items || []" border stripe>
            <el-table-column type="expand">
              <template #default="{ row }">
                <div style="padding: 12px 24px">
                  <el-table :data="row.details" border size="small">
                    <el-table-column prop="inventor_name" label="发明人" min-width="120" />
                    <el-table-column label="贡献比例" width="100" align="center"><template #default="{row:d}">{{ d.contribution_ratio }}%</template></el-table-column>
                    <el-table-column label="奖金金额" width="120" align="right"><template #default="{row:d}">¥{{ d.amount?.toFixed(2) }}</template></el-table-column>
                    <el-table-column label="发放状态" width="80" align="center"><template #default="{row:d}"><el-tag :type="d.payment_status==='已发'?'success':'warning'" size="small">{{ d.payment_status }}</el-tag></template></el-table-column>
                  </el-table>
                </div>
              </template>
            </el-table-column>
            <el-table-column prop="batch_code" label="批次编号" width="150" />
            <el-table-column prop="batch_name" label="批次名称" min-width="150" show-overflow-tooltip />
            <el-table-column prop="department" label="部门" width="100" show-overflow-tooltip />
            <el-table-column prop="milestone" label="里程碑" width="90" align="center" />
            <el-table-column label="应发" width="90" align="right"><template #default="{row}">¥{{ row.approved_amount?.toFixed(2) || '0.00' }}</template></el-table-column>
            <el-table-column label="已发" width="90" align="right"><template #default="{row}">¥{{ row.received_amount?.toFixed(2) || '0.00' }}</template></el-table-column>
            <el-table-column label="本次申请" width="90" align="right"><template #default="{row}">¥{{ row.applied_amount?.toFixed(2) || '0.00' }}</template></el-table-column>
            <el-table-column label="合计" width="100" align="right"><template #default="{row}"><strong style="color:#f56c6c">¥{{ row.total_amount?.toFixed(2) }}</strong></template></el-table-column>
            <el-table-column label="状态" width="80" align="center"><template #default="{row}"><el-tag :type="row.payment_status==='已发'?'success':'warning'" size="small">{{ row.payment_status }}</el-tag></template></el-table-column>
            <el-table-column prop="batch_status" label="批次状态" width="90" align="center"><template #default="{row}"><el-tag size="small" effect="plain">{{ row.batch_status }}</el-tag></template></el-table-column>
          </el-table>
        </el-card>
      </el-tab-pane>

      <!-- Files -->
      <el-tab-pane label="关联文件" name="files">
        <el-card shadow="never">
          <el-upload :action="`/api/files/upload?business_type=patent&business_id=${patentId}`" :headers="uploadHeaders" :on-success="onUploadSuccess" :show-file-list="false" drag style="margin-bottom:16px">
            <el-icon size="40"><UploadFilled /></el-icon>
            <div>点击或拖拽文件上传</div>
            <template #tip><div style="font-size:12px;color:#909399">支持 PDF/Word/Excel/图片，单文件≤100MB</div></template>
          </el-upload>
          <el-table :data="patent.files || []" border stripe size="small">
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
            <el-table-column prop="business_type" label="对象类型" width="100" />
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

    <!-- Fee Dialog -->
    <el-dialog v-model="feeDialogVisible" :title="feeEditing ? '编辑年费' : '添加年费'" width="500px">
      <el-form :model="feeForm" label-width="100px">
        <el-form-item label="年度"><el-input-number v-model="feeForm.fee_year" :min="1" :max="20" /></el-form-item>
        <el-form-item label="应缴日"><el-date-picker v-model="feeForm.due_date" type="date" value-format="YYYY-MM-DD" /></el-form-item>
        <el-form-item label="实缴日"><el-date-picker v-model="feeForm.actual_pay_date" type="date" value-format="YYYY-MM-DD" /></el-form-item>
        <el-form-item label="标准金额"><el-input-number v-model="feeForm.standard_amount" :precision="2" /></el-form-item>
        <el-form-item label="费减金额"><el-input-number v-model="feeForm.reduced_amount" :precision="2" /></el-form-item>
        <el-form-item label="实付金额"><el-input-number v-model="feeForm.actual_pay_amount" :precision="2" /></el-form-item>
        <el-form-item label="状态"><el-select v-model="feeForm.status"><el-option label="待缴" value="待缴" /><el-option label="已缴" value="已缴" /><el-option label="逾期" value="逾期" /></el-select></el-form-item>
        <el-form-item label="收据号"><el-input v-model="feeForm.receipt_no" /></el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="feeDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="saveFee">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted, watch } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { UploadFilled, EditPen, Delete, Download } from '@element-plus/icons-vue'
import api from '../../api'
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { LineChart, BarChart } from 'echarts/charts'
import { TitleComponent, TooltipComponent, LegendComponent, GridComponent } from 'echarts/components'

use([CanvasRenderer, LineChart, BarChart, TitleComponent, TooltipComponent, LegendComponent, GridComponent])

const route = useRoute()
const patentId = parseInt(route.params.id)
const loading = ref(false)
const activeTab = ref('info')
const patent = ref({})
const feeDialogVisible = ref(false)
const feeEditing = ref(false)

const bonusData = ref({ item_count: 0, total_amount: 0, items: [] })
const auditLogs = ref([])
const logsLoading = ref(false)
const logPage = reactive({ page: 1, page_size: 20, total: 0 })

const uploadHeaders = computed(() => ({ Authorization: `Bearer ${localStorage.getItem('token')}` }))

const typeTagType = (t) => ({ '发明': 'primary', '实用新型': 'success', '外观': 'warning', '软著': 'info', '软产': 'danger' }[t] || '')
const statusTagType = (s) => ({ '授权': 'success', '转让': 'success', '驳回终止': 'danger', '驳回复审': 'warning', '撤回': 'info', '审中': 'warning' }[s] || '')

const actionTagType = (a) => ({ 'create': 'success', 'update': 'warning', 'delete': 'danger', 'login': 'info', 'export': 'info' }[a] || '')
const actionLabel = (a) => ({ 'create': '创建', 'update': '修改', 'delete': '删除', 'login': '登录', 'export': '导出' }[a] || a)

const emptyFee = () => ({ fee_year: 1, due_date: null, actual_pay_date: null, standard_amount: null, reduced_amount: null, actual_pay_amount: null, status: '待缴', receipt_no: '', receipt_file_id: null })
const feeForm = ref(emptyFee())

const formatDate = (dt) => {
  if (!dt) return '—'
  return typeof dt === 'string' ? dt.replace('T', ' ').slice(0, 19) : ''
}

const formatSize = (bytes) => {
  if (!bytes) return '—'
  if (bytes < 1024) return bytes + ' B'
  if (bytes < 1048576) return (bytes / 1024).toFixed(1) + ' KB'
  return (bytes / 1048576).toFixed(1) + ' MB'
}

// Fee curve chart
const feeCurveOption = computed(() => {
  const fees = (patent.value.fees || []).slice().sort((a, b) => a.fee_year - b.fee_year)
  return {
    tooltip: {
      trigger: 'axis',
      formatter: (params) => {
        let html = `第${params[0].axisValue}年<br/>`
        params.forEach(p => {
          html += `${p.marker}${p.seriesName}: ¥${p.value}<br/>`
        })
        return html
      }
    },
    legend: { data: ['标准金额', '费减金额', '实付金额'], bottom: 0 },
    grid: { left: '3%', right: '4%', bottom: '12%', containLabel: true },
    xAxis: { type: 'category', data: fees.map(f => '第' + f.fee_year + '年'), axisLabel: { rotate: 0 } },
    yAxis: { type: 'value', name: '金额(元)' },
    series: [
      {
        name: '标准金额', type: 'line', smooth: true,
        data: fees.map(f => f.standard_amount || 0),
        itemStyle: { color: '#409EFF' }
      },
      {
        name: '费减金额', type: 'line', smooth: true,
        data: fees.map(f => f.reduced_amount || 0),
        itemStyle: { color: '#E6A23C' }
      },
      {
        name: '实付金额', type: 'bar',
        data: fees.map(f => f.actual_pay_amount || 0),
        itemStyle: { color: '#67C23A', borderRadius: [4, 4, 0, 0] },
        barWidth: '30%'
      }
    ]
  }
})

// ===== 年费完整性审核 =====
const feeAudit = computed(() => patent.value.fee_audit || null)
const overdueFees = computed(() => (feeAudit.value?.missing || []).filter(m => m.overdue))
const futureFees = computed(() => (feeAudit.value?.missing || []).filter(m => !m.overdue))
const fmtYearList = (arr) => arr.map(m => `第${m.fee_year}年`).join('、')
const feeAuditTagType = computed(() => {
  const a = feeAudit.value
  if (!a || a.complete) return 'success'
  if (a.duplicate_years.length) return 'warning'
  if (a.overdue_count) return 'danger'
  return 'info'
})
const feeAuditSummary = computed(() => {
  const a = feeAudit.value
  if (!a) return ''
  if (a.complete) return '记录完整'
  const parts = []
  if (a.overdue_count) parts.push(`${a.overdue_count} 年已过期未写`)
  if (a.future_count) parts.push(`${a.future_count} 年未到期`)
  if (a.duplicate_years.length) parts.push('有重复')
  return parts.join('，')
})
const completingFees = ref(false)
const completeFees = async () => {
  ElMessageBox.confirm(
    `将按规则自动补写 ${feeAudit.value.missing.length} 个缺失年份的年费记录（状态为「待缴」）。已有记录不会被改动，确认继续？`,
    '一键补写年费', { type: 'warning' }
  ).then(async () => {
    completingFees.value = true
    try {
      const res = await api.post(`/patents/${patentId}/fees/complete`)
      ElMessage.success(res.message || '补写成功')
      loadData()
    } catch (e) {
      console.error(e)
      ElMessage.error('补写失败：' + (e.response?.data?.detail || e.message))
    } finally { completingFees.value = false }
  }).catch(() => {})
}

const loadData = async () => {
  loading.value = true
  try {
    patent.value = await api.get(`/patents/${patentId}`)
  } catch (e) { console.error(e) } finally { loading.value = false }
}

const loadBonusHistory = async () => {
  try {
    bonusData.value = await api.get(`/bonus/patent/${patentId}`)
  } catch (e) { console.error(e) }
}

const loadAuditLogs = async () => {
  logsLoading.value = true
  try {
    const res = await api.get('/reports/audit-logs', {
      params: { ...logPage, business_type: 'patent', business_id: patentId }
    })
    auditLogs.value = res.items
    logPage.total = res.total
  } catch (e) { console.error(e) } finally { logsLoading.value = false }
}

// Watch tab changes to lazy-load data
watch(activeTab, (tab) => {
  if (tab === 'bonus' && bonusData.value.item_count === 0) {
    loadBonusHistory()
  } else if (tab === 'logs' && auditLogs.value.length === 0) {
    loadAuditLogs()
  }
})

const openFeeDialog = () => { feeForm.value = emptyFee(); feeEditing.value = false; feeDialogVisible.value = true }
const editFee = (row) => { feeForm.value = { ...row }; feeEditing.value = true; feeDialogVisible.value = true }

const saveFee = async () => {
  try {
    if (feeEditing.value) {
      await api.put(`/patents/${patentId}/fees/${feeForm.value.id}`, feeForm.value)
    } else {
      await api.post(`/patents/${patentId}/fees`, { ...feeForm.value, patent_id: patentId })
    }
    ElMessage.success('保存成功')
    feeDialogVisible.value = false
    loadData()
  } catch (e) { console.error(e) }
}

const deleteFee = (row) => {
  ElMessageBox.confirm('确定删除这条年费记录？', '确认', { type: 'warning' })
    .then(async () => {
      await api.delete(`/patents/${patentId}/fees/${row.id}`)
      ElMessage.success('已删除')
      loadData()
    }).catch(() => {})
}

const onUploadSuccess = () => { ElMessage.success('上传成功'); loadData() }
const downloadFile = (fid) => { window.open(`/api/files/${fid}/download?token=${localStorage.getItem('token')}`, '_blank') }
const deleteFile = (fid) => {
  ElMessageBox.confirm('确定删除此文件？', '确认', { type: 'warning' })
    .then(async () => { await api.delete(`/files/${fid}`); ElMessage.success('已删除'); loadData() }).catch(() => {})
}

// Official website links
const openExternal = (url) => {
  // noopener,noreferrer 避免 Chrome 拦截弹窗
  window.open(url, '_blank', 'noopener,noreferrer')
}

// Fee file upload - general (for new fee records, stored temporarily)
const beforeFeeFileUpload = (file) => {
  ElMessage.info(`文件 ${file.name} 已选择，请先创建年费记录后为该记录上传凭证`)
  return false  // prevent auto-upload
}

// Fee file upload - for a specific fee record
const beforeFeeRecordFileUpload = async (file, feeRow) => {
  const formData = new FormData()
  formData.append('file', file)
  try {
    const res = await fetch(`/api/files/upload?business_type=patent_fee&business_id=${feeRow.id}`, {
      method: 'POST',
      headers: { 'Authorization': `Bearer ${localStorage.getItem('token')}` },
      body: formData
    })
    if (res.ok) {
      const data = await res.json()
      if (data.id) {
        // Update the fee record with the file id
        await api.put(`/patents/${patentId}/fees/${feeRow.id}`, {
          ...feeRow,
          receipt_file_id: data.id
        })
        ElMessage.success('凭证上传成功')
        loadData()
      }
    } else {
      ElMessage.error('上传失败')
    }
  } catch (e) {
    ElMessage.error('上传失败: ' + e.message)
  }
  return false  // prevent auto-upload
}

// Download/view fee receipt file
const downloadFeeFile = (fileId) => {
  window.open(`/api/files/${fileId}/download?token=${localStorage.getItem('token')}`, '_blank')
}

onMounted(loadData)
</script>

<style scoped>
.official-links {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
}
.action-btns { display: flex; gap: 6px; justify-content: center; }
</style>
