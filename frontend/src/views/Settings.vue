<template>
  <div>
    <el-tabs v-model="activeTab">
      <!-- Account Info -->
      <el-tab-pane label="账户信息" name="account">
        <el-card>
          <el-descriptions :column="1" border style="max-width: 500px">
            <el-descriptions-item label="用户名">{{ user?.username || '—' }}</el-descriptions-item>
            <el-descriptions-item label="姓名">{{ user?.display_name || '—' }}</el-descriptions-item>
            <el-descriptions-item label="邮箱">{{ user?.email || '—' }}</el-descriptions-item>
            <el-descriptions-item label="角色">{{ roleLabel(user?.role) }}</el-descriptions-item>
          </el-descriptions>
          <el-button type="primary" style="margin-top: 16px" @click="pwdDialog = true">修改密码</el-button>
        </el-card>
      </el-tab-pane>

      <!-- User Management -->
      <el-tab-pane label="用户管理" name="users">
        <el-card>
          <template #header>
            <div style="display: flex; justify-content: space-between; align-items: center">
              <span>系统用户</span>
              <el-button type="primary" size="small" @click="userDialog = true; resetUserForm()">新增用户</el-button>
            </div>
          </template>
          <el-table :data="users" stripe v-loading="loadingUsers">
            <el-table-column label="用户名" prop="username" width="120" />
            <el-table-column label="姓名" prop="display_name" width="100" />
            <el-table-column label="邮箱" prop="email" min-width="180" />
            <el-table-column label="角色" prop="role" width="100">
              <template #default="{ row }">
                <el-tag :type="row.role === 'admin' ? 'danger' : row.role === 'member' ? 'primary' : 'info'" size="small">{{ roleLabel(row.role) }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column label="状态" prop="status" width="80">
              <template #default="{ row }">
                <el-tag :type="row.status === 'active' ? 'success' : 'danger'" size="small">{{ row.status === 'active' ? '启用' : '禁用' }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column label="最后登录" prop="last_login_at" width="160">
              <template #default="{ row }">{{ formatDate(row.last_login_at) }}</template>
            </el-table-column>
            <el-table-column label="操作" width="200" align="center">
              <template #default="{ row }">
                <div class="action-btns">
                  <el-tooltip content="编辑" placement="top">
                    <el-button circle size="small" type="warning" plain @click="editUser(row)">
                      <el-icon><EditPen /></el-icon>
                    </el-button>
                  </el-tooltip>
                  <el-tooltip content="重置密码" placement="top">
                    <el-button circle size="small" type="info" plain @click="resetPwd(row)">
                      <el-icon><Key /></el-icon>
                    </el-button>
                  </el-tooltip>
                  <el-tooltip v-if="row.id !== user?.id" content="禁用" placement="top">
                    <el-button circle size="small" type="danger" plain @click="disableUser(row)">
                      <el-icon><Lock /></el-icon>
                    </el-button>
                  </el-tooltip>
                </div>
              </template>
            </el-table-column>
          </el-table>
        </el-card>
      </el-tab-pane>

      <!-- Fee Standard Management -->
      <el-tab-pane label="费用标准" name="standards">
        <el-card v-loading="loadingStd">
          <template #header>
            <div style="display: flex; justify-content: space-between; align-items: center">
              <span>国知局费用标准</span>
              <el-button type="primary" size="small" @click="stdDialog = true; resetStdForm()">新增标准</el-button>
            </div>
          </template>

          <el-alert type="info" :closable="false" show-icon style="margin-bottom: 16px"
            title="费减口径"
            description="上年度应纳税所得额小于 100 万元：按费减 85% 执行（实缴 15%）；大于 100 万元：按标准金额全额缴纳。标注「不予减免」的费用项不参与费减。" />

          <el-row :gutter="16">
            <el-col v-for="g in feeGroups" :key="g.type" :span="12">
              <div class="fee-group">
                <div class="fee-group-title">{{ g.title }}</div>

                <!-- 一次性费用 -->
                <template v-if="g.oneTime.length">
                  <div class="fee-sub-title">申请相关费用</div>
                  <el-table :data="g.oneTime" size="small" border style="margin-bottom: 12px">
                    <el-table-column label="费用项" min-width="140">
                      <template #default="{ row }">
                        <div>{{ row.fee_type }}</div>
                        <div v-if="row.note" class="fee-note" :class="{ 'no-reduce': row.noReduce }">
                          {{ row.noReduce ? '不予减免' : row.note }}
                        </div>
                      </template>
                    </el-table-column>
                    <el-table-column label="标准金额" width="100" align="right">
                      <template #default="{ row }"><span class="fee-amt">¥{{ row.standard_amount }}</span></template>
                    </el-table-column>
                    <el-table-column label="费减85%" width="100" align="right">
                      <template #default="{ row }">
                        <span v-if="!row.noReduce" class="fee-amt fee-reduced">¥{{ row.reduced_85_amount }}</span>
                        <span v-else class="fee-na">—</span>
                      </template>
                    </el-table-column>
                    <el-table-column label="费减70%" width="100" align="right">
                      <template #default="{ row }">
                        <span v-if="!row.noReduce" class="fee-amt fee-reduced">¥{{ row.reduced_70_amount }}</span>
                        <span v-else class="fee-na">—</span>
                      </template>
                    </el-table-column>
                    <el-table-column label="操作" width="88" align="center">
                      <template #default="{ row }">
                        <div class="action-btns">
                          <el-button circle size="small" type="warning" plain @click="editStd(row)">
                            <el-icon><EditPen /></el-icon>
                          </el-button>
                          <el-button circle size="small" type="danger" plain @click="deleteStd(row)">
                            <el-icon><Delete /></el-icon>
                          </el-button>
                        </div>
                      </template>
                    </el-table-column>
                  </el-table>
                  <div class="fee-total-row">
                    <span>小计（全额 / 费减85%）</span>
                    <span>¥{{ g.oneTimeTotal }} / <strong class="fee-reduced">¥{{ g.oneTimeReduced }}</strong></span>
                  </div>
                </template>

                <!-- 年费阶梯 -->
                <template v-if="g.annual.length">
                  <div class="fee-sub-title">年费（按年度阶梯）</div>
                  <el-table :data="g.annual" size="small" border>
                    <el-table-column label="专利年度" width="110" align="center">
                      <template #default="{ row }">
                        <el-tag v-if="row.year_start === row.year_end" size="small" type="info">第{{ row.year_start }}年</el-tag>
                        <el-tag v-else size="small" type="info">第{{ row.year_start }}–{{ row.year_end }}年</el-tag>
                      </template>
                    </el-table-column>
                    <el-table-column label="标准金额" width="100" align="right">
                      <template #default="{ row }"><span class="fee-amt">¥{{ row.standard_amount }}</span></template>
                    </el-table-column>
                    <el-table-column label="费减85%" width="100" align="right">
                      <template #default="{ row }"><span class="fee-amt fee-reduced">¥{{ row.reduced_85_amount }}</span></template>
                    </el-table-column>
                    <el-table-column label="费减70%" width="100" align="right">
                      <template #default="{ row }"><span class="fee-amt fee-reduced">¥{{ row.reduced_70_amount }}</span></template>
                    </el-table-column>
                    <el-table-column label="备注" min-width="90" show-overflow-tooltip>
                      <template #default="{ row }">{{ row.note || '—' }}</template>
                    </el-table-column>
                    <el-table-column label="操作" width="88" align="center">
                      <template #default="{ row }">
                        <div class="action-btns">
                          <el-button circle size="small" type="warning" plain @click="editStd(row)">
                            <el-icon><EditPen /></el-icon>
                          </el-button>
                          <el-button circle size="small" type="danger" plain @click="deleteStd(row)">
                            <el-icon><Delete /></el-icon>
                          </el-button>
                        </div>
                      </template>
                    </el-table-column>
                  </el-table>
                </template>

                <el-empty v-if="!g.oneTime.length && !g.annual.length" description="暂无费用项" :image-size="60" />
              </div>
            </el-col>
          </el-row>
        </el-card>
      </el-tab-pane>

      <!-- Audit Logs -->
      <el-tab-pane label="审计日志" name="logs">
        <el-card>
          <template #header>
            <div style="display: flex; gap: 8px">
              <el-select v-model="logFilter.action" placeholder="操作类型" clearable style="width: 120px" @change="loadLogs">
                <el-option label="创建" value="create" />
                <el-option label="更新" value="update" />
                <el-option label="删除" value="delete" />
                <el-option label="登录" value="login" />
                <el-option label="导出" value="export" />
                <el-option label="导入" value="import" />
              </el-select>
              <el-select v-model="logFilter.business_type" placeholder="业务模块" clearable style="width: 120px" @change="loadLogs">
                <el-option label="专利" value="patent" />
                <el-option label="商标" value="trademark" />
                <el-option label="代理机构" value="agency" />
                <el-option label="用户" value="user" />
                <el-option label="奖金" value="bonus" />
              </el-select>
            </div>
          </template>
          <el-table :data="logs" stripe v-loading="loadingLogs" size="small">
            <el-table-column label="时间" prop="created_at" width="160">
              <template #default="{ row }">{{ formatDate(row.created_at) }}</template>
            </el-table-column>
            <el-table-column label="操作人" prop="user_name" width="100" />
            <el-table-column label="操作" prop="action" width="80">
              <template #default="{ row }">
                <el-tag :type="actionTag(row.action)" size="small">{{ actionLabel(row.action) }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column label="模块" prop="business_type" width="100" />
            <el-table-column label="详情" prop="after_value" min-width="300" show-overflow-tooltip />
          </el-table>
          <div style="margin-top: 12px; display: flex; justify-content: flex-end">
            <el-pagination v-model:current-page="logPage" :total="logTotal" :page-size="20" layout="total, prev, pager, next" @current-change="loadLogs" />
          </div>
        </el-card>
      </el-tab-pane>

      <!-- Data Management -->
      <el-tab-pane label="数据管理" name="data">
        <el-card>
          <template #header><span>示例数据清除</span></template>
          <el-alert type="warning" :closable="false" show-icon style="margin-bottom:16px"
            title="仅部署到公司虚拟机、准备导入真实数据前使用"
            description="点击后将清空系统内所有业务数据（商标、专利、代理机构、奖金、上传文件、审计日志等），仅保留登录账号 admin / user，并在清空前自动备份当前数据库。" />
          <el-button type="danger" :loading="resetting" @click="resetDemo">清除示例数据</el-button>
        </el-card>
      </el-tab-pane>
    </el-tabs>

    <!-- Password Dialog -->
    <el-dialog v-model="pwdDialog" title="修改密码" width="400px">
      <el-form label-width="100px">
        <el-form-item label="当前密码"><el-input v-model="pwdForm.old_password" type="password" show-password /></el-form-item>
        <el-form-item label="新密码"><el-input v-model="pwdForm.new_password" type="password" show-password /></el-form-item>
        <el-form-item label="确认密码"><el-input v-model="pwdForm.confirm" type="password" show-password /></el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="pwdDialog = false">取消</el-button>
        <el-button type="primary" @click="handleChangePwd">确认</el-button>
      </template>
    </el-dialog>

    <!-- User Dialog -->
    <el-dialog v-model="userDialog" :title="userForm.id ? '编辑用户' : '新增用户'" width="500px">
      <el-form :model="userForm" label-width="100px">
        <el-form-item label="用户名"><el-input v-model="userForm.username" :disabled="!!userForm.id" /></el-form-item>
        <el-form-item v-if="!userForm.id" label="密码"><el-input v-model="userForm.password" type="password" show-password /></el-form-item>
        <el-form-item label="姓名"><el-input v-model="userForm.display_name" /></el-form-item>
        <el-form-item label="邮箱"><el-input v-model="userForm.email" /></el-form-item>
        <el-form-item label="角色">
          <el-select v-model="userForm.role">
            <el-option label="管理员" value="admin" />
            <el-option label="部门成员" value="member" />
            <el-option label="只读访客" value="viewer" />
          </el-select>
        </el-form-item>
        <el-form-item v-if="userForm.id" label="状态">
          <el-select v-model="userForm.status">
            <el-option label="启用" value="active" />
            <el-option label="禁用" value="disabled" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="userDialog = false">取消</el-button>
        <el-button type="primary" @click="saveUser">保存</el-button>
      </template>
    </el-dialog>

    <!-- Fee Standard Dialog -->
    <el-dialog v-model="stdDialog" :title="stdForm.id ? '编辑费用标准' : '新增费用标准'" width="600px">
      <el-form :model="stdForm" label-width="100px">
        <el-form-item label="类别">
          <el-select v-model="stdForm.category">
            <el-option label="国内" value="国内" />
            <el-option label="PCT国际" value="PCT国际" />
            <el-option label="外观设计国际" value="外观设计国际" />
            <el-option label="集成电路" value="集成电路" />
          </el-select>
        </el-form-item>
        <el-form-item label="费用类型"><el-input v-model="stdForm.fee_type" placeholder="如：申请费、年费、实质审查费" /></el-form-item>
        <el-form-item label="专利类型">
          <el-select v-model="stdForm.patent_type">
            <el-option label="发明" value="发明" />
            <el-option label="实用新型" value="实用新型" />
            <el-option label="外观" value="外观" />
            <el-option label="软著" value="软著" />
            <el-option label="全部" value="全部" />
          </el-select>
        </el-form-item>
        <el-form-item label="年份起"><el-input-number v-model="stdForm.year_start" :min="1" :max="20" /></el-form-item>
        <el-form-item label="年份止"><el-input-number v-model="stdForm.year_end" :min="1" :max="20" /></el-form-item>
        <el-form-item label="标准金额"><el-input-number v-model="stdForm.standard_amount" :min="0" :precision="2" /></el-form-item>
        <el-form-item label="费减85%"><el-input-number v-model="stdForm.reduced_85_amount" :min="0" :precision="2" /></el-form-item>
        <el-form-item label="费减70%"><el-input-number v-model="stdForm.reduced_70_amount" :min="0" :precision="2" /></el-form-item>
        <el-form-item label="单位"><el-input v-model="stdForm.unit" /></el-form-item>
        <el-form-item label="备注"><el-input v-model="stdForm.note" type="textarea" :rows="2" /></el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="stdDialog = false">取消</el-button>
        <el-button type="primary" @click="saveStd">保存</el-button>
      </template>
    </el-dialog>

    <!-- Reset Password Dialog -->
    <el-dialog v-model="resetPwdDialog" title="重置密码" width="400px">
      <el-form label-width="80px">
        <el-form-item label="用户">{{ resetPwdUser?.display_name }}</el-form-item>
        <el-form-item label="新密码"><el-input v-model="newPwd" type="password" show-password /></el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="resetPwdDialog = false">取消</el-button>
        <el-button type="primary" @click="confirmResetPwd">确认重置</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { EditPen, Delete, Key, Lock } from '@element-plus/icons-vue'
import api from '@/api'

const user = computed(() => {
  try { return JSON.parse(localStorage.getItem('user') || 'null') } catch { return null }
})

const activeTab = ref('account')

// Password
const pwdDialog = ref(false)
const pwdForm = reactive({ old_password: '', new_password: '', confirm: '' })

const handleChangePwd = async () => {
  if (pwdForm.new_password !== pwdForm.confirm) {
    ElMessage.error('两次密码不一致')
    return
  }
  if (pwdForm.new_password.length < 8) {
    ElMessage.error('密码至少8位')
    return
  }
  try {
    await api.put('/auth/change-password', {
      old_password: pwdForm.old_password,
      new_password: pwdForm.new_password
    })
    ElMessage.success('密码修改成功')
    pwdDialog.value = false
    Object.assign(pwdForm, { old_password: '', new_password: '', confirm: '' })
  } catch (e) { console.error(e) }
}

// Users
const users = ref([])
const loadingUsers = ref(false)
const userDialog = ref(false)
const userForm = reactive({ id: null, username: '', password: '', display_name: '', email: '', role: 'member', status: 'active' })

const loadUsers = async () => {
  loadingUsers.value = true
  try {
    const res = await api.get('/admin/users')
    users.value = res.items || []
  } catch (e) { console.error(e) } finally { loadingUsers.value = false }
}

const resetUserForm = () => {
  Object.assign(userForm, { id: null, username: '', password: '', display_name: '', email: '', role: 'member', status: 'active' })
}

const editUser = (row) => {
  Object.assign(userForm, row)
  userDialog.value = true
}

const saveUser = async () => {
  try {
    if (userForm.id) {
      await api.put(`/admin/users/${userForm.id}`, {
        display_name: userForm.display_name,
        email: userForm.email,
        role: userForm.role,
        status: userForm.status
      })
    } else {
      await api.post('/admin/users', userForm)
    }
    ElMessage.success('保存成功')
    userDialog.value = false
    loadUsers()
  } catch (e) { console.error(e) }
}

const resetPwdUser = ref(null)
const resetPwdDialog = ref(false)
const newPwd = ref('')

const resetPwd = (row) => {
  resetPwdUser.value = row
  newPwd.value = ''
  resetPwdDialog.value = true
}

const confirmResetPwd = async () => {
  if (newPwd.value.length < 8) {
    ElMessage.error('密码至少8位')
    return
  }
  try {
    await api.put(`/admin/users/${resetPwdUser.value.id}/password`, { new_password: newPwd.value })
    ElMessage.success('密码已重置')
    resetPwdDialog.value = false
  } catch (e) { console.error(e) }
}

const disableUser = async (row) => {
  try {
    await ElMessageBox.confirm(`确认禁用用户"${row.display_name}"？`, '提示', { type: 'warning' })
    await api.delete(`/admin/users/${row.id}`)
    ElMessage.success('已禁用')
    loadUsers()
  } catch (e) { if (e !== 'cancel') console.error(e) }
}

// Fee Standards
const standards = ref([])
const loadingStd = ref(false)
const stdDialog = ref(false)
const stdForm = reactive({ id: null, category: '国内', fee_type: '', patent_type: '发明', year_start: null, year_end: null, standard_amount: 0, reduced_85_amount: 0, reduced_70_amount: 0, unit: '元', note: '' })

const loadStandards = async () => {
  loadingStd.value = true
  try {
    const res = await api.get('/admin/fee-standards')
    standards.value = res.items || []
  } catch (e) { console.error(e) } finally { loadingStd.value = false }
}

const resetStdForm = () => {
  Object.assign(stdForm, { id: null, category: '国内', fee_type: '', patent_type: '发明', year_start: null, year_end: null, standard_amount: 0, reduced_85_amount: 0, reduced_70_amount: 0, unit: '元', note: '' })
}

const editStd = (row) => {
  Object.assign(stdForm, row)
  stdDialog.value = true
}

const saveStd = async () => {
  if (!stdForm.fee_type) { ElMessage.warning('请输入费用类型'); return }
  try {
    if (stdForm.id) {
      await api.put(`/admin/fee-standards/${stdForm.id}`, stdForm)
    } else {
      await api.post('/admin/fee-standards', stdForm)
    }
    ElMessage.success('保存成功')
    stdDialog.value = false
    loadStandards()
  } catch (e) { console.error(e) }
}

const deleteStd = async (row) => {
  try {
    await ElMessageBox.confirm(`确认删除此费用标准？`, '提示', { type: 'warning' })
    await api.delete(`/admin/fee-standards/${row.id}`)
    ElMessage.success('已删除')
    loadStandards()
  } catch (e) { if (e !== 'cancel') console.error(e) }
}

// 费用标准分组（按专利类型：一次性费用 + 年费阶梯）
const PATENT_TYPE_LABELS = { '发明': '发明', '实用新型': '实用新型', '外观': '外观设计', '软著': '软件著作权 / 软件产品', '软产': '软件著作权 / 软件产品' }

const feeGroups = computed(() => {
  const groups = []
  const byType = {}
  for (const s of standards.value) {
    const key = s.patent_type || '其他'
    if (!byType[key]) byType[key] = { type: key, title: PATENT_TYPE_LABELS[key] || key, oneTime: [], annual: [] }
    s.noReduce = !!(s.note && /不予减免|不减免/.test(s.note))
    if (s.fee_type === '年费') byType[key].annual.push(s)
    else byType[key].oneTime.push(s)
  }
  // 常用类型排前
  const order = ['发明', '实用新型', '外观', '软著', '软产', '全部']
  const keys = Object.keys(byType).sort((a, b) => {
    const ia = order.indexOf(a); const ib = order.indexOf(b)
    return (ia === -1 ? 99 : ia) - (ib === -1 ? 99 : ib)
  })
  for (const k of keys) {
    const g = byType[k]
    g.oneTime.sort((a, b) => (a.fee_type === '申请费' ? -1 : 0) - (b.fee_type === '申请费' ? -1 : 0))
    g.annual.sort((a, b) => (a.year_start || 999) - (b.year_start || 999))
    g.oneTimeTotal = g.oneTime.reduce((s, r) => s + (r.standard_amount || 0), 0)
    // 费减85% 合计 = 可减免项按 reduced_85 + 不予减免项按标准金额（即实缴口径）
    g.oneTimeReduced = g.oneTime.reduce((s, r) => s + (r.noReduce ? (r.standard_amount || 0) : (r.reduced_85_amount || 0)), 0)
    groups.push(g)
  }
  return groups
})

// Audit Logs
const logs = ref([])
const loadingLogs = ref(false)
const logPage = ref(1)
const logTotal = ref(0)
const logFilter = reactive({ action: '', business_type: '' })

const loadLogs = async () => {
  loadingLogs.value = true
  try {
    const res = await api.get('/reports/audit-logs', {
      params: { page: logPage.value, page_size: 20, action: logFilter.action, business_type: logFilter.business_type }
    })
    logs.value = res.items || []
    logTotal.value = res.total || 0
  } catch (e) { console.error(e) } finally { loadingLogs.value = false }
}

// Helpers
const roleLabel = (role) => ({ admin: '管理员', member: '部门成员', viewer: '只读访客' }[role] || role)
const actionLabel = (a) => ({ create: '创建', update: '更新', delete: '删除', login: '登录', export: '导出', import: '导入' }[a] || a)
const actionTag = (a) => ({ create: 'success', update: 'primary', delete: 'danger', login: 'info', export: 'warning', import: 'warning' }[a] || '')
const formatDate = (dt) => dt ? new Date(dt).toLocaleString('zh-CN') : '—'

// Reset demo data
const resetting = ref(false)
const resetDemo = async () => {
  try {
    await ElMessageBox.confirm(
      '确认清除所有示例/业务数据？此操作不可撤销（系统会先自动备份数据库）。清空后仅保留 admin / user 账号。',
      '危险操作确认', { type: 'warning', confirmButtonText: '确认清除', cancelButtonText: '取消' }
    )
  } catch (e) { return }
  resetting.value = true
  try {
    await api.post('/system/reset-demo')
    ElMessage.success('示例数据已清除，仅保留管理员账号（admin / admin123）')
  } catch (e) {
    ElMessage.error('清除失败：' + (e?.response?.data?.detail || e.message))
  } finally {
    resetting.value = false
  }
}

onMounted(() => {
  loadUsers()
  loadStandards()
  loadLogs()
})
</script>

<style scoped>
.action-btns { display: flex; gap: 6px; justify-content: center; }

.fee-group {
  border: 1px solid var(--el-border-color-lighter, #ebeef5);
  border-radius: 8px;
  padding: 12px 14px;
  margin-bottom: 16px;
  background: var(--el-fill-color-blank, #fff);
}
.fee-group-title {
  font-size: 15px;
  font-weight: 600;
  margin-bottom: 10px;
  padding-bottom: 8px;
  border-bottom: 2px solid #409EFF;
  color: var(--el-text-color-primary, #303133);
}
.fee-sub-title {
  font-size: 13px;
  font-weight: 600;
  color: var(--el-text-color-secondary, #606266);
  margin: 6px 0 6px;
}
.fee-note { font-size: 12px; color: #909399; margin-top: 2px; }
.fee-note.no-reduce { color: #F56C6C; }
.fee-amt { font-variant-numeric: tabular-nums; font-weight: 500; }
.fee-reduced { color: #E6A23C; }
.fee-na { color: #c0c4cc; }
.fee-total-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 13px;
  padding: 8px 4px 2px;
  color: var(--el-text-color-regular, #606266);
}
</style>
