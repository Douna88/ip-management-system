<template>
  <div class="ai-assistant">
    <!-- 悬浮球 -->
    <div class="ai-fab" @click="togglePanel" :title="open ? '收起 AI 助手' : '打开 AI 助手'">
      <el-icon :size="26"><ChatDotRound /></el-icon>
      <span class="ai-fab-pulse" v-if="!open"></span>
    </div>

    <transition name="panel">
      <div v-if="open" class="ai-panel">
        <!-- 头部 -->
        <div class="ai-header">
          <div class="ai-title">
            <span class="ai-title-dot" :class="{ on: aiEnabled === true && modelReachable, warn: aiEnabled === true && !modelReachable, off: aiEnabled === false }"></span>
            <span class="ai-title-text">AI 助手</span>
            <el-tag v-if="aiEnabled === true && modelReachable" size="small" type="success" effect="light" round>已连接</el-tag>
            <el-tag v-else-if="aiEnabled === true && !modelReachable" size="small" type="warning" effect="light" round>离线模式</el-tag>
            <el-tag v-else-if="aiEnabled === false" size="small" type="info" effect="light" round>未启用</el-tag>
          </div>
          <el-icon class="ai-close" @click="open = false"><Close /></el-icon>
        </div>

        <!-- 消息区 -->
        <div class="ai-messages" ref="msgBox">
          <!-- 欢迎语 + 推荐问题 -->
          <div class="msg assistant">
            <div class="bubble ai-bubble">
              <div class="bubble-text">你好，我是 IP 管理助手。直接问我系统里的数据：</div>
              <div class="suggestion-list">
                <div class="suggestion-chip" @click="quickAsk('今年申请了多少件发明专利？')">📊 今年发明专利申请数</div>
                <div class="suggestion-chip" @click="quickAsk('有哪些专利被驳回了？')">❌ 被驳回的专利</div>
                <div class="suggestion-chip" @click="quickAsk('年费缴纳情况如何？')">💰 年费缴纳汇总</div>
                <div class="suggestion-chip" @click="quickAsk('有哪些商标已到期需要续展？')">🔖 待续展商标</div>
              </div>
            </div>
          </div>

          <div v-for="(m, i) in messages" :key="i" :class="['msg', m.role]">
            <!-- 用户消息 -->
            <div v-if="m.role === 'user'" class="bubble user-bubble">
              <div class="bubble-text">{{ m.content }}</div>
            </div>

            <!-- AI 回复 -->
            <div v-else class="bubble ai-bubble">
              <div v-if="m.loading" class="ai-loading">
                <el-icon class="is-loading"><Loading /></el-icon>
                <span>正在分析问题并查询数据...</span>
              </div>

              <template v-else>
                <div v-if="m.error || m.message" class="ai-error">
                  <el-icon><WarningFilled /></el-icon>
                  <span>{{ m.error || m.message }}</span>
                </div>

                <template v-else>
                  <!-- 答案来源标记：让用户知道是模型生成的还是内置引擎直出的 -->
                  <div v-if="m.source" class="source-bar">
                    <el-tag v-if="m.source === 'ai'" size="small" type="success" effect="plain">
                      <el-icon><MagicStick /></el-icon> AI 生成
                    </el-tag>
                    <el-tag v-else size="small" type="info" effect="plain">
                      <el-icon><Cpu /></el-icon> 内置查询引擎 · 秒回
                    </el-tag>
                    <span v-if="m.label" class="source-label">{{ m.label }}</span>
                  </div>

                  <!-- 文字解读（重点，置顶） -->
                  <div v-if="m.summary" class="ai-summary">
                    <div class="ai-section-label">
                      <el-icon><ChatLineRound /></el-icon> 解读
                    </div>
                    <div class="ai-summary-text">{{ m.summary }}</div>
                  </div>

                  <!-- 可视化图表 -->
                  <div v-if="m.chart_option" class="ai-chart">
                    <div class="ai-section-label">
                      <el-icon><TrendCharts /></el-icon> 可视化图表
                    </div>
                    <div class="chart-wrap">
                      <v-chart :option="m.chart_option" style="height: 260px" autoresize />
                    </div>
                  </div>

                  <!-- 模型离线说明 -->
                  <div v-if="m.offline_note" class="offline-note">
                    <el-icon><WarningFilled /></el-icon> {{ m.offline_note }}
                  </div>

                  <!-- 未命中规则且模型离线：给出可直接提问的示例 -->
                  <div v-if="m.hint" class="offline-hint">
                    <div class="hint-title">这个问题需要大模型处理，当前无法连接。以下内容仍可直接问：</div>
                    <div class="hint-chips">
                      <span v-for="(s, i) in hintExamples" :key="i" class="hint-chip" @click="askExample(s)">{{ s }}</span>
                    </div>
                  </div>

                  <!-- SQL 块（不展示，用户不需要看技术细节） -->

                  <!-- 结果表格 -->
                  <div v-if="m.result && m.result.length" class="result-block">
                    <div class="ai-section-label">
                      <el-icon><DataAnalysis /></el-icon>
                      查询结果（{{ m.result.length }} 条）
                    </div>
                    <div class="result-table-wrap">
                      <el-table :data="m.result" size="small" border stripe max-height="260" style="width: 100%">
                        <el-table-column
                          v-for="col in Object.keys(m.result[0])"
                          :key="col"
                          :prop="col"
                          :label="col"
                          show-overflow-tooltip
                          min-width="80"
                        />
                      </el-table>
                    </div>
                  </div>
                  <div v-else-if="m.result" class="ai-empty">
                    <el-icon><InfoFilled /></el-icon>
                    <span>查询执行成功，但暂无匹配数据</span>
                  </div>
                </template>
              </template>
            </div>
          </div>
        </div>

        <!-- 输入区 -->
        <div class="ai-input">
          <el-input
            v-model="input"
            placeholder="问我系统里的数据..."
            :disabled="aiEnabled === false"
            @keyup.enter="onEnter"
            @compositionstart="composing = true"
            @compositionend="onCompositionEnd"
            clearable
            size="default"
          />
          <el-button
            type="primary"
            :loading="sending"
            :disabled="aiEnabled === false || !input.trim()"
            @click="send"
            round
          >
            <el-icon><Promotion /></el-icon>
            <span style="margin-left:4px">发送</span>
          </el-button>
        </div>
      </div>
    </transition>
  </div>
</template>

<script setup>
import { ref, nextTick, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import {
  ChatDotRound, Close, Loading, WarningFilled,
  DataAnalysis, Promotion, ChatLineRound, InfoFilled,
  MagicStick, Cpu, TrendCharts
} from '@element-plus/icons-vue'
import api from '../api'
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { BarChart, PieChart, LineChart } from 'echarts/charts'
import { TitleComponent, TooltipComponent, GridComponent, LegendComponent } from 'echarts/components'

use([CanvasRenderer, BarChart, PieChart, LineChart, TitleComponent, TooltipComponent, GridComponent, LegendComponent])

const open = ref(false)
const input = ref('')
const messages = ref([])
const sending = ref(false)
// 中文输入法组合状态：拼音选词期间按 Enter 是"确认候选词"，不能触发发送，
// 否则输入中文时一按回车整句就被发走了（表现为"没法输入中文"）。
const composing = ref(false)
const onEnter = (e) => {
  if (composing.value || e.isComposing) return
  send()
}
const onCompositionEnd = () => {
  // 部分浏览器 compositionend 后紧跟一次 keyup.enter，延迟一帧复位
  setTimeout(() => { composing.value = false }, 0)
}
const aiEnabled = ref(null)
const modelReachable = ref(true)
const msgBox = ref(null)

const scrollToBottom = async () => {
  await nextTick()
  if (msgBox.value) msgBox.value.scrollTop = msgBox.value.scrollHeight
}

const checkStatus = async () => {
  try {
    const res = await api.get('/ai/status')
    aiEnabled.value = !!res.enabled
    modelReachable.value = res.reachable !== false
  } catch (e) {
    aiEnabled.value = false
    modelReachable.value = false
  }
}

const togglePanel = () => {
  open.value = !open.value
  if (open.value) scrollToBottom()
}

const quickAsk = (text) => {
  input.value = text
  send()
}

const askExample = (text) => {
  input.value = text
  send()
}

// 模型离线时可直接使用内置引擎回答的示例
const hintExamples = [
  '谁2025年奖金超过5000',
  '2025年奖金总额',
  '谁奖金最多',
  '专利总数',
  '发明专利有多少件',
  '待缴年费还有多少',
  '商标总数',
  '近期有哪些年费快到期了'
]

const send = async () => {
  const text = input.value.trim()
  if (!text || sending.value) return
  input.value = ''
  messages.value.push({ role: 'user', content: text })
  messages.value.push({ role: 'assistant', loading: true })
  scrollToBottom()

  sending.value = true
  try {
    const res = await api.post('/ai/query', { question: text })
    const last = messages.value[messages.value.length - 1]
    last.loading = false
    if (res.error) {
      last.error = res.error
      last.hint = res.hint || null
      last.offline = !!res.offline
    } else if (!res.enabled) {
      last.message = res.message || 'AI 功能未启用'
    } else {
      last.sql = res.sql
      last.result = res.result
      last.summary = res.summary
      last.source = res.source || null
      last.label = res.label || null
      last.offline_note = res.offline_note || null
      last.chart_option = res.chart_option || null
    }
  } catch (e) {
    const last = messages.value[messages.value.length - 1]
    last.loading = false
    last.error = '请求失败，请稍后重试'
  } finally {
    sending.value = false
    scrollToBottom()
  }
}

onMounted(checkStatus)
</script>

<style scoped>
.ai-assistant {
  position: fixed;
  right: 28px;
  bottom: 28px;
  z-index: 2000;
}

/* 悬浮球 */
.ai-fab {
  width: 56px;
  height: 56px;
  border-radius: 50%;
  background: linear-gradient(135deg, #409EFF 0%, #2566c8 100%);
  color: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  box-shadow: 0 8px 24px rgba(64, 158, 255, 0.42);
  position: relative;
  transition: transform 0.25s cubic-bezier(0.16, 1, 0.3, 1), box-shadow 0.25s;
}
.ai-fab:hover {
  transform: scale(1.08);
  box-shadow: 0 12px 32px rgba(64, 158, 255, 0.6);
}
.ai-fab-pulse {
  position: absolute;
  top: 4px;
  right: 4px;
  width: 10px;
  height: 10px;
  border-radius: 50%;
  background: #f56c6c;
  border: 2px solid #fff;
  animation: pulse 2s infinite;
}
@keyframes pulse {
  0%, 100% { transform: scale(1); opacity: 1; }
  50% { transform: scale(1.2); opacity: 0.7; }
}

/* 面板 */
.ai-panel {
  position: absolute;
  right: 0;
  bottom: 70px;
  width: 460px;
  height: 600px;
  max-height: calc(100vh - 120px);
  background: #fff;
  border-radius: 16px;
  box-shadow: 0 16px 48px rgba(0, 0, 0, 0.18), 0 0 0 1px rgba(0, 0, 0, 0.04);
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

/* 头部 */
.ai-header {
  height: 56px;
  padding: 0 18px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  background: linear-gradient(180deg, #fafbfc 0%, #f5f7fa 100%);
  border-bottom: 1px solid #ebeef5;
}
.ai-title {
  display: flex;
  align-items: center;
  gap: 8px;
}
.ai-title-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #c0c4cc;
}
.ai-title-dot.on { background: #67c23a; box-shadow: 0 0 0 3px rgba(103, 194, 58, 0.2); }
.ai-title-dot.off { background: #909399; }
.ai-title-dot.warn { background: #e6a23c; box-shadow: 0 0 0 3px rgba(230, 162, 60, 0.2); }
.ai-title-text {
  font-weight: 600;
  font-size: 15px;
  color: #303133;
}
.ai-close {
  cursor: pointer;
  color: #909399;
  font-size: 18px;
  padding: 4px;
  border-radius: 4px;
  transition: all 0.2s;
}
.ai-close:hover { color: #303133; background: rgba(0, 0, 0, 0.04); }

/* 消息区 */
.ai-messages {
  flex: 1;
  overflow-y: auto;
  padding: 16px;
  display: flex;
  flex-direction: column;
  gap: 14px;
  background: #f7f8fa;
  scrollbar-width: thin;
}
.ai-messages::-webkit-scrollbar { width: 6px; }
.ai-messages::-webkit-scrollbar-thumb { background: #c0c4cc; border-radius: 3px; }

.msg { display: flex; }
.msg.user { justify-content: flex-end; }
.msg.assistant { justify-content: flex-start; }

/* 气泡 */
.bubble {
  max-width: 88%;
  font-size: 13.5px;
  line-height: 1.6;
  word-break: break-word;
}
.user-bubble {
  background: linear-gradient(135deg, #409EFF 0%, #2b7fd6 100%);
  color: #fff;
  padding: 10px 14px;
  border-radius: 14px;
  border-bottom-right-radius: 4px;
  box-shadow: 0 2px 8px rgba(64, 158, 255, 0.25);
}
.ai-bubble {
  background: #fff;
  color: #303133;
  border: 1px solid #ebeef5;
  padding: 12px 14px;
  border-radius: 14px;
  border-bottom-left-radius: 4px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.04);
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.bubble-text { font-size: 13.5px; line-height: 1.65; }

/* 推荐问题 */
.suggestion-list {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-top: 8px;
}
.suggestion-chip {
  font-size: 12px;
  padding: 5px 10px;
  background: #f0f5ff;
  color: #409EFF;
  border-radius: 12px;
  cursor: pointer;
  transition: all 0.2s;
  border: 1px solid transparent;
}
.suggestion-chip:hover {
  background: #409EFF;
  color: #fff;
  transform: translateY(-1px);
  box-shadow: 0 2px 6px rgba(64, 158, 255, 0.3);
}

/* 加载 */
.ai-loading {
  display: flex;
  align-items: center;
  gap: 8px;
  color: #909399;
  font-size: 13px;
  padding: 4px 0;
}

/* 错误 */
.ai-error {
  display: flex;
  align-items: flex-start;
  gap: 6px;
  color: #f56c6c;
  font-size: 13px;
  line-height: 1.6;
  padding: 6px 10px;
  background: #fef0f0;
  border-radius: 6px;
}

/* 空 */
.ai-empty {
  display: flex;
  align-items: center;
  gap: 6px;
  color: #909399;
  font-size: 13px;
  padding: 8px 0;
}

/* 区块标签 */
.ai-section-label {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 11.5px;
  color: #909399;
  font-weight: 500;
  letter-spacing: 0.3px;
}
.ai-section-label .el-icon { color: #c0c4cc; }

/* 文字解读 */
/* 答案来源标记 */
.source-bar {
  display: flex; align-items: center; gap: 8px;
  margin-bottom: 8px; flex-wrap: wrap;
}
.source-bar :deep(.el-icon) { vertical-align: -2px; margin-right: 3px; }
.source-label { font-size: 12px; color: #909399; }

/* 离线说明 */
.offline-note {
  display: flex; align-items: center; gap: 6px;
  margin-top: 8px; padding: 6px 10px;
  font-size: 12px; color: #E6A23C;
  background: #fdf6ec; border-radius: 4px;
}

/* 离线时的可用示例 */
.offline-hint {
  margin-top: 10px; padding: 10px 12px;
  background: #f8f9fa; border-radius: 6px; border: 1px dashed #e4e7ed;
}

.ai-chart {
  margin-top: 10px;
  background: #fff;
  border: 1px solid #f0f2f5;
  border-radius: 6px;
  padding: 8px 8px 0;
}
.chart-wrap {
  width: 100%;
}

.ai-chart :deep(.v-chart) {
  border-radius: 4px;
}
.hint-title { font-size: 12px; color: #606266; margin-bottom: 8px; line-height: 1.5; }
.hint-chips { display: flex; flex-wrap: wrap; gap: 6px; }
.hint-chip {
  font-size: 12px; color: #409EFF; background: #ecf5ff;
  padding: 3px 9px; border-radius: 10px; cursor: pointer;
  transition: all 0.2s cubic-bezier(0.16, 1, 0.3, 1);
}
.hint-chip:hover { background: #409EFF; color: #fff; transform: translateY(-1px); }

.ai-summary {
  padding: 10px 12px;
  background: linear-gradient(135deg, #f0f7ff 0%, #e6f0ff 100%);
  border-left: 3px solid #409EFF;
  border-radius: 6px;
}
.ai-summary-text {
  margin-top: 4px;
  font-size: 13.5px;
  line-height: 1.7;
  color: #303133;
}

/* 结果表格 */
.result-block { display: flex; flex-direction: column; gap: 6px; }
.result-table-wrap {
  border-radius: 6px;
  overflow: hidden;
  border: 1px solid #ebeef5;
}
.result-table-wrap :deep(.el-table) {
  font-size: 12.5px;
}
.result-table-wrap :deep(.el-table th) {
  background: #fafbfc !important;
  color: #606266;
  font-weight: 600;
}

/* 输入区 */
.ai-input {
  padding: 12px 16px 14px;
  border-top: 1px solid #ebeef5;
  display: flex;
  gap: 8px;
  background: #fff;
  align-items: center;
}
.ai-input :deep(.el-input__wrapper) {
  border-radius: 22px;
  padding: 4px 16px;
  background: #f5f7fa;
  box-shadow: none !important;
  transition: all 0.2s;
}
.ai-input :deep(.el-input__wrapper:hover) {
  background: #eef0f4;
}
.ai-input :deep(.el-input.is-focus .el-input__wrapper) {
  background: #fff;
  box-shadow: 0 0 0 2px rgba(64, 158, 255, 0.2) !important;
}

/* 面板动画 */
.panel-enter-active, .panel-leave-active {
  transition: all 0.28s cubic-bezier(0.16, 1, 0.3, 1);
}
.panel-enter-from, .panel-leave-to {
  opacity: 0;
  transform: translateY(20px) scale(0.96);
}
</style>
