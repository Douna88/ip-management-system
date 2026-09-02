<template>
  <div class="patent-bonus-page">
    <!-- Bonus Rule Info -->
    <el-card shadow="never" class="rule-card" v-if="currentRule">
      <div class="rule-header">
        <el-icon><Trophy /></el-icon>
        <span class="rule-name">{{ currentRule.rule_name }}</span>
        <el-tag size="small" type="success" effect="dark">当前生效</el-tag>
      </div>
      <div class="rule-grid">
        <div v-for="(val, key) in currentRule.rules_parsed" :key="key" class="rule-item">
          <span class="rule-type">{{ key }}</span>
          <div class="rule-amounts">
            <span v-for="(amt, milestone) in val" :key="milestone" class="rule-amount">
              {{ milestone }}: <strong>¥{{ amt }}</strong>
            </span>
          </div>
        </div>
      </div>
    </el-card>

    <!-- Visualization Section -->
    <el-card shadow="never" class="bonus-viz-card" style="margin-bottom: 16px">
      <template #header>
        <div class="viz-header">
          <div class="viz-title">
            <el-icon :size="20" color="#E6A23C"><TrendCharts /></el-icon>
            <span>奖金数据可视化</span>
          </div>
          <el-select v-model="bonusYear" @change="loadBonusStats" size="small" style="width: 110px">
            <el-option label="累计" value="all" />
            <el-option v-for="y in yearOptions" :key="y" :label="y + '年'" :value="y" />
          </el-select>
        </div>
      </template>

      <!-- Key metrics -->
      <el-row :gutter="12" style="margin-bottom: 16px">
        <el-col :span="6" v-for="m in bonusMetrics" :key="m.label">
          <div class="metric-card" :style="{ '--accent': m.color }">
            <div class="metric-icon"><el-icon :size="22"><component :is="m.icon" /></el-icon></div>
            <div class="metric-body">
              <div class="metric-label">{{ m.label }}</div>
              <div class="metric-value">{{ formatMoney(m.value) }}</div>
            </div>
          </div>
        </el-col>
      </el-row>

      <!-- Chart row 1: by_type pie + top10 inventors bar -->
      <el-row :gutter="12" style="margin-bottom: 16px">
        <el-col :span="12">
          <div class="chart-title">按专利类型分布</div>
          <v-chart :option="typeChartOption" style="height: 280px" autoresize />
        </el-col>
        <el-col :span="12">
          <div class="chart-title">发明人奖金 TOP10</div>
          <v-chart :option="top10ChartOption" style="height: 280px" autoresize />
        </el-col>
      </el-row>

      <!-- Chart row 2: yearly trend + monthly trend -->
      <el-row :gutter="12" style="margin-bottom: 16px">
        <el-col :span="12">
          <div class="chart-title">年度奖金趋势（应发/已发/申请）</div>
          <v-chart :option="yearlyChartOption" style="height: 280px" autoresize />
        </el-col>
        <el-col :span="12">
          <div class="chart-title">月度发放趋势</div>
          <v-chart :option="monthlyChartOption" style="height: 280px" autoresize />
        </el-col>
      </el-row>

      <!-- Chart row 3: by department bar + dept detail table -->
      <el-row :gutter="12" style="margin-bottom: 16px">
        <el-col :span="12">
          <div class="chart-title">部门奖金分布</div>
          <v-chart :option="deptChartOption" style="height: 280px" autoresize />
        </el-col>
        <el-col :span="12">
          <div class="chart-title">部门奖金明细</div>
          <el-table :data="deptDetailData" border stripe size="small" style="max-height: 280px; overflow-y: auto">
            <el-table-column type="index" label="#" width="50" align="center" />
            <el-table-column prop="name" label="部门" min-width="120" />
            <el-table-column label="应发奖金" width="110" align="right">
              <template #default="{ row }">¥{{ row.approved?.toFixed(2) || '0.00' }}</template>
            </el-table-column>
            <el-table-column label="已发奖金" width="110" align="right">
              <template #default="{ row }">¥{{ row.received?.toFixed(2) || '0.00' }}</template>
            </el-table-column>
            <el-table-column label="申请发放" width="110" align="right">
              <template #default="{ row }">¥{{ row.applied?.toFixed(2) || '0.00' }}</template>
            </el-table-column>
            <el-table-column label="合计" width="110" align="right">
              <template #default="{ row }"><strong style="color:#f56c6c">¥{{ row.total?.toFixed(2) || '0.00' }}</strong></template>
            </el-table-column>
          </el-table>
        </el-col>
      </el-row>

      <!-- Chart row 4: by batch status + all inventors table -->
      <el-row :gutter="12" style="margin-bottom: 16px">
        <el-col :span="12">
          <div class="chart-title">批次状态统计</div>
          <v-chart :option="batchStatusChartOption" style="height: 280px" autoresize />
        </el-col>
        <el-col :span="12">
          <div class="chart-title">发明人奖金明细</div>
          <el-table :data="bonusStats.all_inventors || []" border stripe size="small" style="max-height: 280px; overflow-y: auto">
            <el-table-column type="index" label="#" width="50" align="center" />
            <el-table-column prop="name" label="发明人" min-width="120" />
            <el-table-column label="奖金金额" width="120" align="right">
              <template #default="{ row }">¥{{ row.amount?.toFixed(2) }}</template>
            </el-table-column>
          </el-table>
        </el-col>
      </el-row>
    </el-card>

    <!-- Toolbar -->
    <div class="toolbar">
      <div class="toolbar-left">
        <el-select v-model="batchFilter.status" placeholder="状态筛选" clearable style="width: 130px" @change="loadBatches">
          <el-option label="草稿" value="草稿" />
          <el-option label="审批中" value="审批中" />
          <el-option label="已批准" value="已批准" />
          <el-option label="已发放" value="已发放" />
        </el-select>
      </div>
      <div class="toolbar-right">
        <el-upload
          ref="uploadRef"
          :show-file-list="false"
          :http-request="handleExcelUpload"
          accept=".xlsx,.xls"
        >
          <el-button type="success" :loading="importing">
            <el-icon><Upload /></el-icon> 导入Excel奖金表
          </el-button>
        </el-upload>
        <el-button type="primary" @click="openCreateDialog">
          <el-icon><Plus /></el-icon> 新建奖金批次
        </el-button>
      </div>
    </div>

    <!-- Batch List -->
    <el-card shadow="never">
      <el-table :data="batches" v-loading="loading" border stripe style="width: 100%">
        <el-table-column prop="batch_code" label="批次编号" width="170" />
        <el-table-column prop="batch_name" label="批次名称" min-width="180" show-overflow-tooltip />
        <el-table-column prop="rule_name" label="适用规则" width="180" show-overflow-tooltip />
        <el-table-column label="统计周期" width="200" align="center">
          <template #default="{ row }">
            {{ row.period_start }} ~ {{ row.period_end }}
          </template>
        </el-table-column>
        <el-table-column prop="item_count" label="专利数" width="80" align="center" />
        <el-table-column label="总金额" width="120" align="right">
          <template #default="{ row }">
            <span class="amount-text">¥{{ row.total_amount?.toFixed(2) || '0.00' }}</span>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="90" align="center">
          <template #default="{ row }">
            <el-tag :type="batchStatusType(row.status)" size="small" effect="dark">{{ row.status }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="属性" width="80" align="center">
          <template #default="{ row }">
            <el-tag :type="row.read_only ? 'info' : 'warning'" size="small" effect="plain">
              {{ row.read_only ? '只读' : '可编辑' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="created_at" label="创建时间" width="160" align="center">
          <template #default="{ row }">{{ formatDate(row.created_at) }}</template>
        </el-table-column>
        <el-table-column label="操作" width="240" align="center" fixed="right">
          <template #default="{ row }">
            <div class="action-btns">
              <el-tooltip content="详情" placement="top">
                <el-button circle size="small" type="primary" plain @click="viewBatchDetail(row.id)">
                  <el-icon><View /></el-icon>
                </el-button>
              </el-tooltip>
              <el-tooltip content="导出Excel" placement="top">
                <el-button circle size="small" type="success" plain @click="exportBatch(row.id)">
                  <el-icon><Download /></el-icon>
                </el-button>
              </el-tooltip>
              <el-tooltip v-if="row.status === '草稿'" content="提交审批" placement="top">
                <el-button circle size="small" type="info" plain @click="changeStatus(row.id, '审批中')">
                  <el-icon><Promotion /></el-icon>
                </el-button>
              </el-tooltip>
              <el-tooltip v-if="row.status === '审批中'" content="批准" placement="top">
                <el-button circle size="small" type="success" plain @click="changeStatus(row.id, '已批准')">
                  <el-icon><Check /></el-icon>
                </el-button>
              </el-tooltip>
              <el-tooltip v-if="row.status === '已批准'" content="标记发放" placement="top">
                <el-button circle size="small" type="primary" plain @click="changeStatus(row.id, '已发放')">
                  <el-icon><Money /></el-icon>
                </el-button>
              </el-tooltip>
              <el-tooltip v-if="row.status === '草稿'" content="删除" placement="top">
                <el-button circle size="small" type="danger" plain @click="deleteBatch(row.id)">
                  <el-icon><Delete /></el-icon>
                </el-button>
              </el-tooltip>
            </div>
          </template>
        </el-table-column>
      </el-table>
      <el-pagination
        class="pagination"
        v-model:current-page="batchFilter.page"
        v-model:page-size="batchFilter.page_size"
        :total="batchTotal"
        :page-sizes="[20, 50]"
        layout="total, prev, pager, next"
        @current-change="loadBatches"
      />
    </el-card>

    <!-- Create Batch Dialog -->
    <el-dialog v-model="createDialogVisible" title="新建奖金批次" width="520px">
      <el-form :model="createForm" label-width="100px">
        <el-form-item label="批次名称" required>
          <el-input v-model="createForm.batch_name" placeholder="例: 2026年上半年专利奖金" />
        </el-form-item>
        <el-form-item label="奖金规则" required>
          <el-select v-model="createForm.rule_id" placeholder="选择规则" style="width: 100%">
            <el-option v-for="r in rules" :key="r.id" :label="r.rule_name" :value="r.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="统计周期" required>
          <el-date-picker
            v-model="createForm.period_range"
            type="daterange"
            range-separator="至"
            start-placeholder="开始日期"
            end-placeholder="结束日期"
            value-format="YYYY-MM-DD"
            style="width: 100%"
          />
        </el-form-item>
        <el-alert type="info" :closable="false" show-icon>
          系统将自动查找该周期内受理/授权的专利，按规则计算奖金并分配到发明人。
        </el-alert>
      </el-form>
      <template #footer>
        <el-button @click="createDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="creating" @click="confirmCreate">创建批次</el-button>
      </template>
    </el-dialog>

    <!-- Batch Detail Dialog (Excel format) -->
    <el-dialog
      v-model="detailDialogVisible"
      :title="detailData ? `批次详情: ${detailData.batch_code}` : ''"
      width="95%"
      top="3vh"
      @close="detailData = null"
    >
      <div v-if="detailData" class="detail-container">
        <!-- Batch Summary -->
        <div class="detail-summary">
          <el-descriptions :column="4" border>
            <el-descriptions-item label="批次名称">{{ detailData.batch_name }}</el-descriptions-item>
            <el-descriptions-item label="适用规则">{{ detailData.rule_name }}</el-descriptions-item>
            <el-descriptions-item label="统计周期">{{ detailData.period_start }} ~ {{ detailData.period_end }}</el-descriptions-item>
            <el-descriptions-item label="状态">
              <el-tag :type="batchStatusType(detailData.status)" size="small" effect="dark">{{ detailData.status }}</el-tag>
            </el-descriptions-item>
            <el-descriptions-item label="专利数">{{ detailData.items?.length || 0 }} 件</el-descriptions-item>
            <el-descriptions-item label="总金额">
              <span class="amount-text" style="font-size: 18px;">¥{{ detailData.total_amount?.toFixed(2) || '0.00' }}</span>
            </el-descriptions-item>
            <el-descriptions-item label="创建时间">{{ formatDate(detailData.created_at) }}</el-descriptions-item>
            <el-descriptions-item label="批次编号">{{ detailData.batch_code }}</el-descriptions-item>
          </el-descriptions>
        </div>

        <!-- Read-only banner for historical batches -->
        <el-alert
          v-if="detailData.read_only"
          type="warning"
          show-icon
          :closable="false"
          style="margin-top: 12px"
        >
          此为历史批次（2026年前），数据仅供查看，不可修改。
        </el-alert>

        <!-- Add item button for editable batches -->
        <div v-if="!detailData.read_only" style="margin-top: 12px; text-align: right">
          <el-button type="primary" size="small" @click="openAddItemDialog">
            <el-icon><Plus /></el-icon> 添加奖金条目
          </el-button>
        </div>

        <!-- Items Table - Excel Format (12 columns) -->
        <el-table
          :data="detailData.items"
          border
          stripe
          style="width: 100%; margin-top: 12px"
          max-height="500"
          :row-class-name="tableRowClassName"
        >
          <el-table-column type="index" label="No." width="55" align="center" fixed />
          <el-table-column prop="patent_name" label="Name" min-width="180" show-overflow-tooltip fixed />
          <el-table-column prop="patent_type" label="Type" width="80" align="center" />
          <el-table-column prop="application_no" label="Applied Number" width="140" show-overflow-tooltip />
          <el-table-column prop="application_date" label="Applied Date" width="110" align="center" />
          <el-table-column prop="issued_date" label="Issued Date" width="110" align="center" />
          <el-table-column prop="department" label="R&D Department" width="110" show-overflow-tooltip />
          <el-table-column label="The Bonus Approved" width="130" align="right">
            <template #default="{ row }">
              <span v-if="!isEditingItem(row)">{{ formatMoney(row.approved_amount) }}</span>
              <el-input-number v-else v-model="editItemForm.approved_amount" :controls="false" size="small" style="width: 100%" />
            </template>
          </el-table-column>
          <el-table-column label="Received Bonus" width="120" align="right">
            <template #default="{ row }">
              <span v-if="!isEditingItem(row)">{{ formatMoney(row.received_amount) }}</span>
              <el-input-number v-else v-model="editItemForm.received_amount" :controls="false" size="small" style="width: 100%" />
            </template>
          </el-table-column>
          <el-table-column label="Applied Bonus" width="120" align="right">
            <template #default="{ row }">
              <span v-if="!isEditingItem(row)" class="amount-text">{{ formatMoney(row.applied_amount) }}</span>
              <el-input-number v-else v-model="editItemForm.applied_amount" :controls="false" size="small" style="width: 100%" />
            </template>
          </el-table-column>
          <el-table-column label="Inventor" min-width="140" show-overflow-tooltip>
            <template #default="{ row }">
              <span v-if="!isEditingItem(row)">{{ row.inventor_str || '-' }}</span>
              <el-input v-else v-model="editItemForm.inventor_str" size="small" placeholder="多个发明人用逗号分隔" />
            </template>
          </el-table-column>
          <el-table-column label="Status" width="90" align="center">
            <template #default="{ row }">
              <el-tag v-if="!isEditingItem(row)" :type="row.payment_status === '已发' ? 'success' : 'warning'" size="small">
                {{ row.payment_status }}
              </el-tag>
              <el-select v-else v-model="editItemForm.bonus_status" size="small" style="width: 100%">
                <el-option label="待发" value="待发" />
                <el-option label="已发" value="已发" />
              </el-select>
            </template>
          </el-table-column>
          <el-table-column v-if="!detailData.read_only" label="操作" width="150" align="center" fixed="right">
            <template #default="{ row }">
              <div class="action-btns" v-if="!isEditingItem(row)">
                <el-tooltip content="编辑" placement="top">
                  <el-button circle size="small" type="primary" plain @click="startEditItem(row)">
                    <el-icon><Edit /></el-icon>
                  </el-button>
                </el-tooltip>
                <el-tooltip v-if="row.payment_status === '待发' && detailData.status === '已批准'" content="标记已发" placement="top">
                  <el-button circle size="small" type="success" plain @click="markItemPaid(row.id)">
                    <el-icon><Money /></el-icon>
                  </el-button>
                </el-tooltip>
                <el-tooltip content="删除" placement="top">
                  <el-button circle size="small" type="danger" plain @click="deleteItem(row)">
                    <el-icon><Delete /></el-icon>
                  </el-button>
                </el-tooltip>
              </div>
              <div class="action-btns" v-else>
                <el-tooltip content="保存" placement="top">
                  <el-button circle size="small" type="success" plain @click="saveEditItem(row)">
                    <el-icon><Check /></el-icon>
                  </el-button>
                </el-tooltip>
                <el-tooltip content="取消" placement="top">
                  <el-button circle size="small" type="info" plain @click="cancelEditItem">
                    <el-icon><Close /></el-icon>
                  </el-button>
                </el-tooltip>
              </div>
            </template>
          </el-table-column>
        </el-table>

        <!-- Summary row -->
        <div class="detail-summary-row" v-if="detailData.items?.length">
          <el-descriptions :column="5" border style="margin-top: 12px">
            <el-descriptions-item label="合计条目数">{{ detailData.items.length }}</el-descriptions-item>
            <el-descriptions-item label="应发奖金合计">
              <span class="amount-text">¥{{ sumField(detailData.items, 'approved_amount').toFixed(2) }}</span>
            </el-descriptions-item>
            <el-descriptions-item label="已发奖金合计">
              <span class="amount-text">¥{{ sumField(detailData.items, 'received_amount').toFixed(2) }}</span>
            </el-descriptions-item>
            <el-descriptions-item label="本次申请合计">
              <span class="amount-text">¥{{ sumField(detailData.items, 'applied_amount').toFixed(2) }}</span>
            </el-descriptions-item>
            <el-descriptions-item label="批次总额">
              <span class="amount-text" style="font-size: 16px;">¥{{ detailData.total_amount?.toFixed(2) || '0.00' }}</span>
            </el-descriptions-item>
          </el-descriptions>
        </div>
      </div>
    </el-dialog>

    <!-- Add Item Dialog -->
    <el-dialog v-model="addItemDialogVisible" title="添加奖金条目" width="600px">
      <el-form :model="addItemForm" label-width="130px">
        <el-form-item label="关联专利">
          <el-select
            v-model="addItemForm.patent_id"
            filterable
            remote
            clearable
            placeholder="搜索专利名称或申请号"
            :remote-method="searchPatents"
            :loading="patentSearching"
            style="width: 100%"
            @change="onPatentSelected"
          >
            <el-option
              v-for="p in patentOptions"
              :key="p.id"
              :label="`${p.patent_name} (${p.application_no})`"
              :value="p.id"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="专利名称" required>
          <el-input v-model="addItemForm.patent_name" placeholder="专利名称" />
        </el-form-item>
        <el-form-item label="专利类型">
          <el-select v-model="addItemForm.patent_type" style="width: 100%">
            <el-option label="发明" value="发明" />
            <el-option label="实用新型" value="实用新型" />
            <el-option label="外观" value="外观" />
            <el-option label="软著" value="软著" />
            <el-option label="软产" value="软产" />
          </el-select>
        </el-form-item>
        <el-form-item label="研发部门">
          <el-input v-model="addItemForm.department" placeholder="如: 研发一部" />
        </el-form-item>
        <el-form-item label="应发奖金">
          <el-input-number v-model="addItemForm.approved_amount" :controls="false" :min="0" style="width: 100%" />
        </el-form-item>
        <el-form-item label="已发奖金">
          <el-input-number v-model="addItemForm.received_amount" :controls="false" :min="0" style="width: 100%" />
        </el-form-item>
        <el-form-item label="本次申请发放">
          <el-input-number v-model="addItemForm.applied_amount" :controls="false" :min="0" style="width: 100%" />
        </el-form-item>
        <el-form-item label="发明人">
          <el-input v-model="addItemForm.inventor_str" placeholder="多个发明人用逗号分隔，如: 张三,李四" />
        </el-form-item>
        <el-form-item label="状态">
          <el-select v-model="addItemForm.bonus_status" style="width: 100%">
            <el-option label="待发" value="待发" />
            <el-option label="已发" value="已发" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="addItemDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="addingItem" @click="confirmAddItem">添加</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  Trophy, Plus, View, Delete, Promotion, Check, Money,
  Upload, Download, Edit, Close, TrendCharts, Coin, Wallet
} from '@element-plus/icons-vue'
import api from '../../api'
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { PieChart, BarChart, LineChart } from 'echarts/charts'
import { TitleComponent, TooltipComponent, LegendComponent, GridComponent } from 'echarts/components'

use([CanvasRenderer, PieChart, BarChart, LineChart, TitleComponent, TooltipComponent, LegendComponent, GridComponent])

const loading = ref(false)
const creating = ref(false)
const importing = ref(false)
const addingItem = ref(false)
const batches = ref([])
const batchTotal = ref(0)
const rules = ref([])
const currentRule = ref(null)
const bonusStats = ref({})

const bonusMetrics = computed(() => {
  const k = bonusStats.value.key_metrics || {}
  const cumulative = bonusYear.value === 'all'
  return [
    { label: '累计奖金总额', value: k.total_amount || 0, color: '#409EFF', icon: Trophy },
    { label: cumulative ? '累计合计（批次口径）' : '本年奖金', value: k.this_year_amount || 0, color: '#67C23A', icon: TrendCharts },
    { label: '应发奖金', value: k.total_approved || 0, color: '#E6A23C', icon: Coin },
    { label: '已发奖金', value: k.total_received || 0, color: '#F56C6C', icon: Wallet }
  ]
})

const batchFilter = reactive({ status: '', page: 1, page_size: 20 })

const currentYear = new Date().getFullYear()
const bonusYear = ref(currentYear)
const yearOptions = [2020, 2021, 2022, 2023, 2024, 2025, currentYear, currentYear + 1].filter((v, i, a) => a.indexOf(v) === i).sort((a, b) => b - a)

const createDialogVisible = ref(false)
const createForm = reactive({
  batch_name: '',
  rule_id: null,
  period_range: []
})

const detailDialogVisible = ref(false)
const detailData = ref(null)

// Edit item state
const editingItemId = ref(null)
const editItemForm = reactive({
  patent_name: '',
  patent_type: '',
  department: '',
  approved_amount: 0,
  received_amount: 0,
  applied_amount: 0,
  inventor_str: '',
  bonus_status: '待发'
})

// Add item dialog state
const addItemDialogVisible = ref(false)
const addItemForm = reactive({
  patent_id: null,
  patent_name: '',
  patent_type: '发明',
  department: '',
  approved_amount: 0,
  received_amount: 0,
  applied_amount: 0,
  inventor_str: '',
  bonus_status: '待发'
})
const patentOptions = ref([])
const patentSearching = ref(false)

const batchStatusType = (status) => {
  const map = { '草稿': 'info', '审批中': 'warning', '已批准': 'success', '已发放': 'primary' }
  return map[status] || ''
}

const formatDate = (dt) => {
  if (!dt) return '-'
  return typeof dt === 'string' ? dt.replace('T', ' ').slice(0, 19) : ''
}

const formatMoney = (val) => {
  if (val === null || val === undefined || val === 0) return '0.00'
  return val.toFixed(2)
}

const sumField = (items, field) => {
  return items.reduce((sum, item) => sum + (item[field] || 0), 0)
}

const isEditingItem = (row) => {
  return editingItemId.value === row.id
}

const tableRowClassName = ({ row }) => {
  if (isEditingItem(row)) return 'editing-row'
  return ''
}

// ===== Data loading =====
const loadRules = async () => {
  try {
    const res = await api.get('/bonus/rules')
    rules.value = res
    currentRule.value = res.find(r => r.is_current) || res[0] || null
    if (currentRule.value && currentRule.value.rule_config) {
      try {
        currentRule.value.rules_parsed = typeof currentRule.value.rule_config === 'string'
          ? JSON.parse(currentRule.value.rule_config)
          : currentRule.value.rule_config
      } catch { currentRule.value.rules_parsed = {} }
    }
  } catch (e) { /* handled */ }
}

const loadBatches = async () => {
  loading.value = true
  try {
    const params = { page: batchFilter.page, page_size: batchFilter.page_size }
    if (batchFilter.status) params.status = batchFilter.status
    const res = await api.get('/bonus/batches', { params })
    batches.value = res.items
    batchTotal.value = res.total
  } catch (e) { /* handled */ } finally {
    loading.value = false
  }
}

const loadBonusStats = async () => {
  try {
    const params = bonusYear.value === 'all' ? {} : { year: bonusYear.value }
    const res = await api.get('/reports/bonus-stats', { params })
    bonusStats.value = res
  } catch (e) { console.error(e) }
}

// ===== Excel Upload =====
const handleExcelUpload = async (options) => {
  const { file } = options
  importing.value = true
  try {
    const formData = new FormData()
    formData.append('file', file)
    const res = await api.post('/io/import/old-bonus', formData, {
      headers: { 'Content-Type': 'multipart/form-data' }
    })
    ElMessage.success(res.message || '导入成功')
    loadBatches()
    loadBonusStats()
  } catch (e) {
    // error handled by interceptor
  } finally {
    importing.value = false
  }
}

// ===== Export =====
const exportBatch = async (batchId) => {
  try {
    const response = await api.get(`/io/export/bonus/${batchId}`, {
      responseType: 'blob'
    })
    const url = window.URL.createObjectURL(new Blob([response]))
    const link = document.createElement('a')
    link.href = url
    link.setAttribute('download', `奖金明细_${Date.now()}.xlsx`)
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
    window.URL.revokeObjectURL(url)
  } catch (e) {
    ElMessage.error('导出失败')
  }
}

// ===== Chart Options =====
const typeChartOption = computed(() => {
  const types = bonusStats.value.by_type || {}
  const chartData = Object.entries(types).filter(([, v]) => v > 0).map(([name, value]) => ({ name, value }))
  return {
    tooltip: { trigger: 'item', formatter: '{b}: ¥{c} ({d}%)' },
    legend: { bottom: 0, type: 'scroll' },
    series: [{
      type: 'pie', radius: ['40%', '70%'], center: ['50%', '45%'],
      data: chartData,
      label: { formatter: '{b}\n¥{c}' },
      itemStyle: { borderRadius: 8, borderColor: '#fff', borderWidth: 2 }
    }]
  }
})

const top10ChartOption = computed(() => {
  const top10 = bonusStats.value.top10_inventors || []
  return {
    tooltip: { trigger: 'axis', formatter: '{b}<br/>¥{c}' },
    grid: { left: '3%', right: '4%', bottom: '3%', containLabel: true },
    xAxis: { type: 'value' },
    yAxis: { type: 'category', data: top10.map(t => t.name).reverse(), axisLabel: { width: 80, overflow: 'truncate' } },
    series: [{
      type: 'bar',
      data: top10.map(t => t.amount).reverse(),
      itemStyle: { color: '#409EFF', borderRadius: [0, 4, 4, 0] },
      label: { show: true, position: 'right', formatter: '¥{c}' }
    }]
  }
})

const monthlyChartOption = computed(() => {
  const monthly = bonusStats.value.monthly_trend || []
  const allZero = monthly.every(m => !m.amount)
  return {
    tooltip: { trigger: 'axis', formatter: '{b}<br/>¥{c}' },
    grid: { left: '3%', right: '4%', bottom: '3%', containLabel: true },
    graphic: allZero ? [{
      type: 'text', left: 'center', top: 'middle',
      style: { text: '该口径下暂无发放日期数据（仅统计有实际发放日期的条目）', fill: '#909399', fontSize: 12 }
    }] : [],
    xAxis: { type: 'category', data: monthly.map(m => m.label || (m.month + '月')) },
    yAxis: { type: 'value' },
    series: [{
      type: 'line',
      data: monthly.map(m => m.amount),
      smooth: true,
      areaStyle: { opacity: 0.3 },
      itemStyle: { color: '#E6A23C' }
    }]
  }
})

const batchStatusChartOption = computed(() => {
  const statuses = bonusStats.value.by_batch_status || {}
  const chartData = Object.entries(statuses).map(([name, val]) => ({ name, value: val.count }))
  return {
    tooltip: { trigger: 'axis' },
    grid: { left: '3%', right: '4%', bottom: '3%', containLabel: true },
    xAxis: { type: 'category', data: chartData.map(d => d.name) },
    yAxis: { type: 'value', minInterval: 1 },
    series: [{
      type: 'bar',
      data: chartData.map(d => d.value),
      itemStyle: {
        color: (params) => ({ '草稿': '#909399', '审批中': '#E6A23C', '已批准': '#67C23A', '已发放': '#409EFF' }[params.name] || '#409EFF'),
        borderRadius: [4, 4, 0, 0]
      },
      barWidth: '40%',
      label: { show: true, position: 'top' }
    }]
  }
})

const deptChartOption = computed(() => {
  const depts = bonusStats.value.by_department || {}
  const entries = Object.entries(depts).filter(([, v]) => v > 0).sort((a, b) => b[1] - a[1])
  return {
    tooltip: { trigger: 'axis', formatter: '{b}<br/>¥{c}' },
    grid: { left: '3%', right: '4%', bottom: '3%', containLabel: true },
    xAxis: { type: 'value' },
    yAxis: { type: 'category', data: entries.map(e => e[0]), axisLabel: { width: 80, overflow: 'truncate' } },
    series: [{
      type: 'bar',
      data: entries.map(e => e[1]),
      itemStyle: { color: '#67C23A', borderRadius: [0, 4, 4, 0] },
      label: { show: true, position: 'right', formatter: '¥{c}' }
    }]
  }
})

const yearlyChartOption = computed(() => {
  const yearly = bonusStats.value.by_year || []
  return {
    tooltip: {
      trigger: 'axis',
      formatter: (params) => {
        let html = `${params[0].axisValue}年<br/>`
        params.forEach(p => {
          html += `${p.marker}${p.seriesName}: ¥${p.value?.toFixed(2) || '0.00'}<br/>`
        })
        return html
      }
    },
    legend: { data: ['应发奖金', '已发奖金', '申请发放'], bottom: 0 },
    grid: { left: '3%', right: '4%', bottom: '12%', containLabel: true },
    xAxis: { type: 'category', data: yearly.map(y => y.year + '') },
    yAxis: { type: 'value', name: '金额(元)' },
    series: [
      {
        name: '应发奖金', type: 'bar',
        data: yearly.map(y => y.approved || 0),
        itemStyle: { color: '#409EFF', borderRadius: [4, 4, 0, 0] },
        barWidth: '20%'
      },
      {
        name: '已发奖金', type: 'bar',
        data: yearly.map(y => y.received || 0),
        itemStyle: { color: '#67C23A', borderRadius: [4, 4, 0, 0] },
        barWidth: '20%'
      },
      {
        name: '申请发放', type: 'line', smooth: true,
        data: yearly.map(y => y.applied || 0),
        itemStyle: { color: '#E6A23C' },
        areaStyle: { opacity: 0.2 }
      }
    ]
  }
})

const deptDetailData = computed(() => {
  const detail = bonusStats.value.dept_detail || {}
  return Object.entries(detail).map(([name, val]) => ({
    name,
    approved: val.approved || 0,
    received: val.received || 0,
    applied: val.applied || 0,
    total: val.total || 0
  })).sort((a, b) => b.total - a.total)
})

// ===== Create Batch =====
const openCreateDialog = () => {
  createForm.batch_name = ''
  createForm.rule_id = currentRule.value?.id || null
  const now = new Date()
  createForm.period_range = [
    `${now.getFullYear()}-01-01`,
    `${now.getFullYear()}-06-30`
  ]
  createDialogVisible.value = true
}

const confirmCreate = async () => {
  if (!createForm.batch_name) {
    ElMessage.warning('请输入批次名称')
    return
  }
  if (!createForm.rule_id) {
    ElMessage.warning('请选择奖金规则')
    return
  }
  if (!createForm.period_range || createForm.period_range.length !== 2) {
    ElMessage.warning('请选择统计周期')
    return
  }

  creating.value = true
  try {
    const res = await api.post('/bonus/batches', {
      batch_name: createForm.batch_name,
      rule_id: createForm.rule_id,
      period_start: createForm.period_range[0],
      period_end: createForm.period_range[1]
    })
    ElMessage.success(res.message || '批次创建成功')
    createDialogVisible.value = false
    loadBatches()
    loadBonusStats()
  } catch (e) { /* handled */ } finally {
    creating.value = false
  }
}

// ===== View Batch Detail =====
const viewBatchDetail = async (id) => {
  try {
    const res = await api.get(`/bonus/batches/${id}`)
    detailData.value = res
    detailDialogVisible.value = true
  } catch (e) { /* handled */ }
}

// ===== Status Change =====
const changeStatus = async (id, status) => {
  try {
    await ElMessageBox.confirm(`确认将批次状态变更为「${status}」？`, '确认', { type: 'warning' })
    await api.put(`/bonus/batches/${id}/status`, { status })
    ElMessage.success('状态已更新')
    loadBatches()
    loadBonusStats()
  } catch (e) { /* cancelled or error */ }
}

const deleteBatch = async (id) => {
  try {
    await ElMessageBox.confirm('确认删除该奖金批次？此操作不可恢复。', '危险操作', { type: 'error' })
    await api.delete(`/bonus/batches/${id}`)
    ElMessage.success('批次已删除')
    loadBatches()
    loadBonusStats()
  } catch (e) { /* cancelled or error */ }
}

// ===== Item Payment =====
const markItemPaid = async (itemId) => {
  try {
    await api.put(`/bonus/items/${itemId}/payment`, { payment_status: '已发' })
    ElMessage.success('已标记为已发放')
    if (detailData.value) {
      viewBatchDetail(detailData.value.id)
    }
  } catch (e) { /* handled */ }
}

// ===== Item Edit =====
const startEditItem = (row) => {
  editingItemId.value = row.id
  editItemForm.patent_name = row.patent_name
  editItemForm.patent_type = row.patent_type
  editItemForm.department = row.department || ''
  editItemForm.approved_amount = row.approved_amount || 0
  editItemForm.received_amount = row.received_amount || 0
  editItemForm.applied_amount = row.applied_amount || 0
  editItemForm.inventor_str = row.inventor_str || ''
  editItemForm.bonus_status = row.payment_status || '待发'
}

const cancelEditItem = () => {
  editingItemId.value = null
}

const saveEditItem = async (row) => {
  try {
    await api.put(`/bonus/items/${row.id}`, {
      patent_name: editItemForm.patent_name,
      patent_type: editItemForm.patent_type,
      department: editItemForm.department,
      approved_amount: editItemForm.approved_amount,
      received_amount: editItemForm.received_amount,
      applied_amount: editItemForm.applied_amount,
      inventor_str: editItemForm.inventor_str,
      bonus_status: editItemForm.bonus_status
    })
    ElMessage.success('条目已更新')
    editingItemId.value = null
    if (detailData.value) {
      viewBatchDetail(detailData.value.id)
    }
  } catch (e) { /* handled */ }
}

// ===== Item Delete =====
const deleteItem = async (row) => {
  try {
    await ElMessageBox.confirm(`确认删除奖金条目「${row.patent_name}」？`, '危险操作', { type: 'error' })
    await api.delete(`/bonus/items/${row.id}`)
    ElMessage.success('条目已删除')
    if (detailData.value) {
      viewBatchDetail(detailData.value.id)
    }
  } catch (e) { /* cancelled or error */ }
}

// ===== Add Item =====
const openAddItemDialog = () => {
  addItemForm.patent_id = null
  addItemForm.patent_name = ''
  addItemForm.patent_type = '发明'
  addItemForm.department = ''
  addItemForm.approved_amount = 0
  addItemForm.received_amount = 0
  addItemForm.applied_amount = 0
  addItemForm.inventor_str = ''
  addItemForm.bonus_status = '待发'
  patentOptions.value = []
  addItemDialogVisible.value = true
}

const searchPatents = async (query) => {
  if (!query) {
    patentOptions.value = []
    return
  }
  patentSearching.value = true
  try {
    const res = await api.get('/patents', {
      params: { search: query, page: 1, page_size: 20 }
    })
    patentOptions.value = res.items || []
  } catch (e) {
    patentOptions.value = []
  } finally {
    patentSearching.value = false
  }
}

const onPatentSelected = (patentId) => {
  const pat = patentOptions.value.find(p => p.id === patentId)
  if (pat) {
    addItemForm.patent_name = pat.patent_name
    addItemForm.patent_type = pat.patent_type || '发明'
    addItemForm.inventor_str = pat.inventors || ''
  }
}

const confirmAddItem = async () => {
  if (!addItemForm.patent_name) {
    ElMessage.warning('请输入专利名称')
    return
  }
  addingItem.value = true
  try {
    await api.post(`/bonus/batches/${detailData.value.id}/items`, {
      patent_id: addItemForm.patent_id,
      patent_name: addItemForm.patent_name,
      patent_type: addItemForm.patent_type,
      department: addItemForm.department,
      approved_amount: addItemForm.approved_amount,
      received_amount: addItemForm.received_amount,
      applied_amount: addItemForm.applied_amount,
      inventor_str: addItemForm.inventor_str,
      bonus_status: addItemForm.bonus_status
    })
    ElMessage.success('奖金条目已添加')
    addItemDialogVisible.value = false
    if (detailData.value) {
      viewBatchDetail(detailData.value.id)
    }
  } catch (e) { /* handled */ } finally {
    addingItem.value = false
  }
}

onMounted(() => {
  loadRules()
  loadBatches()
  loadBonusStats()
})
</script>

<style scoped>
.rule-card { margin-bottom: 16px; }
.rule-header { display: flex; align-items: center; gap: 8px; margin-bottom: 12px; font-size: 16px; }
.rule-header .el-icon { color: #e6a23c; font-size: 20px; }
.rule-name { font-weight: bold; }
.rule-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(240px, 1fr)); gap: 12px; }
.rule-item { background: #f5f7fa; border-radius: 8px; padding: 12px; }
.rule-type { font-size: 14px; font-weight: bold; color: #303133; display: block; margin-bottom: 6px; }
.rule-amounts { display: flex; flex-wrap: wrap; gap: 8px; }
.rule-amount { font-size: 13px; color: #606266; }
.rule-amount strong { color: #f56c6c; }
.chart-title { font-size: 14px; font-weight: bold; margin-bottom: 8px; color: #303133; }
.toolbar { display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px; }
.toolbar-right { display: flex; gap: 8px; }
.pagination { margin-top: 16px; justify-content: flex-end; }
.amount-text { color: #f56c6c; font-weight: bold; }
.detail-container { padding: 0 8px; }
.action-btns { display: flex; gap: 6px; justify-content: center; }
.viz-header { display: flex; justify-content: space-between; align-items: center; }
.viz-title { display: flex; align-items: center; gap: 8px; font-size: 16px; font-weight: 600; color: #303133; }
.bonus-viz-card :deep(.el-card__header) { padding: 14px 18px; }
.metric-card {
  background: #fff; border-radius: 12px; padding: 16px; display: flex; align-items: center; gap: 12px;
  box-shadow: 0 2px 8px rgba(0,0,0,0.04); border-top: 3px solid var(--accent); transition: transform 0.2s;
}
.metric-card:hover { transform: translateY(-2px); }
.metric-icon { width: 42px; height: 42px; border-radius: 10px; background: var(--accent); color: #fff; display: flex; align-items: center; justify-content: center; flex-shrink: 0; }
.metric-body { flex: 1; min-width: 0; }
.metric-label { font-size: 13px; color: #909399; margin-bottom: 4px; }
.metric-value { font-size: 20px; font-weight: 700; color: #303133; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
:deep(.editing-row) {
  background-color: #fdf6ec !important;
}
:deep(.editing-row .el-table__cell) {
  background-color: #fdf6ec !important;
}
</style>
