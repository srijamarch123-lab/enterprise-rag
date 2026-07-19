import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"
import { Shield, UserX, UserCheck, Search, Users, LogIn, AlertTriangle, Clock, Eye, ClipboardList } from "lucide-react"
import api, { getUsers, getStats, getLoginActivity, updateRole, disableUser, enableUser } from "../services/api"
import { useState } from "react"
import { User } from "../types"
import { useTheme } from "../ThemeContext"

const ROLES = ["admin", "hr", "manager", "employee"]

const ACTION_COLORS: Record<string, { bg: string; color: string }> = {
  login:          { bg: '#e8f5ee', color: '#1a5c2e' },
  logout:         { bg: '#f0f0f0', color: '#555' },
  role_change:    { bg: '#fff3cd', color: '#856404' },
  disable_user:   { bg: '#fee', color: '#c00' },
  enable_user:    { bg: '#e8f5ee', color: '#1a5c2e' },
  force_logout:   { bg: '#fde8e8', color: '#a00' },
  password_reset: { bg: '#e8f0fe', color: '#1a56c2' },
  upload:         { bg: '#e0f2fe', color: '#0369a1' },
  search:         { bg: '#fae8ff', color: '#a21caf' },
  submit_feedback: { bg: '#fef3c7', color: '#d97706' },
}

export default function UsersPage() {
  const { theme, isDark } = useTheme()
  const { color, font, radius } = theme
  const qc = useQueryClient()
  const [search, setSearch] = useState("")
  const [activeTab, setActiveTab] = useState<'users' | 'logs'>('users')
  const [selectedLog, setSelectedLog] = useState<any | null>(null)
  const [logPage, setLogPage] = useState(0)
  const [logFilterAction, setLogFilterAction] = useState('')
  const [logSearchUser, setLogSearchUser] = useState('')
  const logLimit = 15

  const { data: stats } = useQuery({
    queryKey: ["stats"],
    queryFn: getStats,
    refetchInterval: 30000,
  })

  const { data: users = [] as User[], isLoading } = useQuery<User[]>({
    queryKey: ["users"],
    queryFn: getUsers,
    refetchInterval: 30000,
  })

  const { data: auditLogs = [], isLoading: logsLoading } = useQuery({
    queryKey: ["auditLogs", logPage, logFilterAction],
    queryFn: async () => {
      const actionParam = logFilterAction ? `&action=${logFilterAction}` : ''
      const res = await api.get(`/admin/audit-logs?skip=${logPage * logLimit}&limit=${logLimit}${actionParam}`)
      return res.data
    },
    enabled: activeTab === 'logs',
  })


  const { data: loginActivity = [], isLoading: loginLoading, error: loginError } = useQuery({
    queryKey: ["loginActivity"],
    queryFn: getLoginActivity,
    refetchInterval: 30000,
  })


  console.log("loginActivity:", loginActivity, "error:", loginError)

  const roleMut = useMutation({
    mutationFn: ({ id, role, department }: { id: number; role: string; department?: string | null }) => updateRole(id, role, department ?? undefined),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["users"] }),
  })

  const disableMut = useMutation({
    mutationFn: (id: number) => disableUser(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["users"] })
      qc.invalidateQueries({ queryKey: ["stats"] })
    },
  })

  const enableMut = useMutation({
    mutationFn: (id: number) => enableUser(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["users"] })
      qc.invalidateQueries({ queryKey: ["stats"] })
    },
  })

  const filteredUsers = users.filter(
    (u: User) =>
      !search || u.email.toLowerCase().includes(search.toLowerCase())
  )

  const filteredLogs = auditLogs.filter((log: any) => {
    if (!logSearchUser) return true
    const email = log.user_email || ''
    return email.toLowerCase().includes(logSearchUser.toLowerCase())
  })


  return (
    <div className="p-8">
      {/* Stats Dashboard */}
      <div className="mb-8">
        <h2 className="text-lg font-semibold text-gray-800 mb-4">Dashboard Overview</h2>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <div className="bg-white border border-gray-200 rounded-xl p-4">
            <div className="flex items-center gap-3">
              <Users className="text-indigo-600" size={20} />
              <div>
                <p className="text-2xl font-bold text-gray-900">{stats?.total_users ?? 0}</p>
                <p className="text-xs text-gray-500">Total Users</p>
              </div>
            </div>
          </div>
          <div className="bg-white border border-gray-200 rounded-xl p-4">
            <div className="flex items-center gap-3">
              <UserCheck className="text-green-600" size={20} />
              <div>
                <p className="text-2xl font-bold text-gray-900">{stats?.active_users ?? 0}</p>
                <p className="text-xs text-gray-500">Active Users</p>
              </div>
            </div>
          </div>
          <div className="bg-white border border-gray-200 rounded-xl p-4">
            <div className="flex items-center gap-3">
              <LogIn className="text-blue-600" size={20} />
              <div>
                <p className="text-2xl font-bold text-gray-900">{stats?.logins_today ?? 0}</p>
                <p className="text-xs text-gray-500">Logins Today</p>
              </div>
            </div>
          </div>
          <div className="bg-white border border-gray-200 rounded-xl p-4">
            <div className="flex items-center gap-3">
              <AlertTriangle className="text-red-600" size={20} />
              <div>
                <p className="text-2xl font-bold text-gray-900">{stats?.failed_attempts_today ?? 0}</p>
                <p className="text-xs text-gray-500">Failed Today</p>
              </div>
            </div>
          </div>
        </div>

        {/* Users by role */}
        <div className="mt-4 flex gap-3">
          {Object.entries(stats?.users_by_role || {}).map(([role, count]: [string, any]) => (
            <div key={role} className="bg-gray-50 border border-gray-200 rounded-lg px-3 py-2 text-xs">
              <span className="font-medium text-indigo-600">{role}:</span>{" "}
              <span className="text-gray-700">{count}</span>
            </div>
          ))}
        </div>
      </div>

      {/* Sub-tabs */}
      <div className="flex gap-4 border-b border-gray-200 mb-6">
        <button
          onClick={() => setActiveTab('users')}
          className={`pb-2 text-sm font-semibold border-b-2 transition-all ${activeTab === 'users' ? 'border-indigo-600 text-indigo-600' : 'border-transparent text-gray-500 hover:text-gray-700'}`}
        >
          Users & Login Activity
        </button>
        <button
          onClick={() => setActiveTab('logs')}
          className={`pb-2 text-sm font-semibold border-b-2 transition-all ${activeTab === 'logs' ? 'border-indigo-600 text-indigo-600' : 'border-transparent text-gray-500 hover:text-gray-700'}`}
        >
          Detailed Activity Logs
        </button>
      </div>

      {activeTab === 'users' && (
        <>
          {/* Recent Login Activity */}
      {loginLoading ? (
        <p className="text-gray-400 mb-4">Loading activity...</p>
      ) : (
        <div className="mb-6">
          <h3 className="text-md font-semibold text-gray-800 mb-3 flex items-center gap-2">
            <Clock size={18} className="text-indigo-600" />
            Recent Login Activity
            <span className="text-xs text-gray-500 font-normal">({loginActivity?.length || 0} records)</span>
            {loginError && <span className="text-red-500 text-xs font-normal">- Error loading</span>}
          </h3>
          <div className="bg-white border border-gray-200 rounded-xl overflow-hidden">
            <div className="max-h-48 overflow-y-auto">
              <table className="w-full text-sm">
                <thead className="bg-gray-50 border-b border-gray-200 sticky top-0">
                  <tr>
                    <th className="text-left px-4 py-2 font-medium text-gray-600">User</th>
                    <th className="text-left px-4 py-2 font-medium text-gray-600">Action</th>
                    <th className="text-left px-4 py-2 font-medium text-gray-600">Time</th>
                    <th className="text-left px-4 py-2 font-medium text-gray-600">IP</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-100">
                  {loginActivity && loginActivity.length > 0 ? (
                    loginActivity.slice(0, 10).map((log: any, i: number) => (
                      <tr key={i} className="hover:bg-gray-50">
                        <td className="px-4 py-2 text-gray-800">{log.user_email || log.user_id}</td>
                        <td className="px-4 py-2">
                          <span className={`text-xs px-2 py-0.5 rounded ${
                            log.action === "login" ? "bg-green-100 text-green-700" : 
                            log.action === "logout" ? "bg-gray-100 text-gray-700" : 
                            "bg-red-100 text-red-700"
                          }`}>
                            {log.action}
                          </span>
                        </td>
                        <td className="px-4 py-2 text-gray-500 text-xs">
                          {log.timestamp ? new Date(log.timestamp).toLocaleString() : "-"}
                        </td>
                        <td className="px-4 py-2 text-gray-500 text-xs font-mono">
                          {log.ip_address || "-"}
                        </td>
                      </tr>
                    ))
                  ) : (
                    <tr>
                      <td colSpan={4} className="px-4 py-4 text-center text-gray-400">
                        No login activity yet
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}


      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-3">
          <Shield className="text-indigo-600" size={24} />
          <h1 className="text-2xl font-bold text-gray-900">User Management</h1>
        </div>

        {/* Search */}
        <div className="relative">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" size={16} />
          <input
            type="text"
            placeholder="Search by email..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="pl-9 pr-4 py-2 border border-gray-200 rounded-lg text-sm focus:ring-2 focus:ring-indigo-500 focus:outline-none w-64"
          />
        </div>
      </div>

      {isLoading ? (
        <p className="text-gray-400">Loading...</p>
      ) : (
        <div className="bg-white border border-gray-200 rounded-xl overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-gray-50 border-b border-gray-200">
                <tr>
                  <th className="text-left px-4 py-3 font-medium text-gray-600">Email</th>
                  <th className="text-left px-4 py-3 font-medium text-gray-600">Name</th>
                  <th className="text-left px-4 py-3 font-medium text-gray-600">Role</th>
                  <th className="text-left px-4 py-3 font-medium text-gray-600">Department</th>
                  <th className="text-left px-4 py-3 font-medium text-gray-600">Status</th>
                  <th className="text-left px-4 py-3 font-medium text-gray-600">Created</th>
                  <th className="text-left px-4 py-3 font-medium text-gray-600">Last Login</th>
                  <th className="text-left px-4 py-3 font-medium text-gray-600">IP</th>
                  <th className="text-left px-4 py-3 font-medium text-gray-600">Logins</th>
                  <th className="text-left px-4 py-3 font-medium text-gray-600">Pwd Changed</th>
                  <th className="text-left px-4 py-3 font-medium text-gray-600">Recent Activity</th>
                  <th className="px-4 py-3" />
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {filteredUsers.map((u: User) => (
                  <tr key={u.id} className={`hover:bg-gray-50 ${!u.is_active ? "opacity-50" : ""}`}>
                    <td className="px-4 py-3 font-medium text-gray-800">{u.email}</td>
                    <td className="px-4 py-3 text-gray-600">{u.full_name ?? "-"}</td>
                    <td className="px-4 py-3">
                      <select
                        value={u.role}
                        onChange={(e) => roleMut.mutate({ id: u.id, role: e.target.value, department: u.department })}
                        disabled={!u.is_active}
                        className="border border-gray-200 rounded px-2 py-1 text-xs focus:ring-1 focus:ring-indigo-500 focus:outline-none"
                      >
                        {ROLES.map((r) => (
                          <option key={r} value={r}>{r}</option>
                        ))}
                      </select>
                    </td>
                    <td className="px-4 py-3">
                      <input
                        type="text"
                        defaultValue={u.department ?? ""}
                        onBlur={(e) => roleMut.mutate({ id: u.id, role: u.role, department: e.target.value })}
                        disabled={!u.is_active}
                        placeholder="e.g. HR, Finance"
                        className="border border-gray-200 rounded px-2 py-1 text-xs focus:ring-1 focus:ring-indigo-500 focus:outline-none w-24"
                      />
                    </td>
                    <td className="px-4 py-3">
                      <span className={`text-xs font-medium px-2 py-0.5 rounded ${u.is_active ? "bg-green-100 text-green-700" : "bg-red-100 text-red-700"}`}>
                        {u.is_active ? "Active" : "Disabled"}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-gray-400 text-xs">
                      {u.created_at ? new Date(u.created_at).toLocaleDateString() : "-"}
                    </td>
                    <td className="px-4 py-3 text-gray-400 text-xs">
                      {u.last_login ? new Date(u.last_login).toLocaleString() : "Never"}
                    </td>
                    <td className="px-4 py-3 text-gray-500 text-xs font-mono">
                      {u.last_login_ip ?? "-"}
                    </td>
                    <td className="px-4 py-3 text-gray-600 text-xs">
                      {u.login_count ?? 0}
                    </td>
                    <td className="px-4 py-3 text-gray-400 text-xs">
                      {u.password_last_changed ? new Date(u.password_last_changed).toLocaleDateString() : "-"}
                    </td>
                    <td className="px-4 py-3 text-gray-500 text-xs">
                      {u.recent_activity?.slice(0, 2).map((a: any, i: number) => (
                        <div key={i} className="truncate">{a.action}</div>
                      )) ?? "-"}
                    </td>
                    <td className="px-4 py-3">
                      {u.is_active ? (
                        <button
                          onClick={() => disableMut.mutate(u.id)}
                          className="p-1 text-red-400 hover:text-red-600 hover:bg-red-50 rounded"
                          title="Disable user"
                        >
                          <UserX size={15} />
                        </button>
                      ) : (
                        <button
                          onClick={() => enableMut.mutate(u.id)}
                          className="p-1 text-green-400 hover:text-green-600 hover:bg-green-50 rounded"
                          title="Enable user"
                        >
                          <UserCheck size={15} />
                        </button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </>
  )}

    {/* Detailed Activity Logs Tab */}
    {activeTab === 'logs' && (
      <div>
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 mb-6">
          <div className="flex items-center gap-3">
            <ClipboardList className="text-indigo-600" size={24} />
            <h1 className="text-2xl font-bold text-gray-900">Activity Logs</h1>
          </div>
          <div className="flex items-center gap-3">
            {/* Search user email */}
            <div className="relative">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" size={16} />
              <input
                type="text"
                placeholder="Filter by user email..."
                value={logSearchUser}
                onChange={(e) => setLogSearchUser(e.target.value)}
                className="pl-9 pr-4 py-2 border border-gray-200 rounded-lg text-sm focus:ring-2 focus:ring-indigo-500 focus:outline-none w-64 bg-white text-gray-950"
              />
            </div>
            {/* Action Filter */}
            <select
              value={logFilterAction}
              onChange={(e) => {
                setLogFilterAction(e.target.value)
                setLogPage(0)
              }}
              className="border border-gray-200 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-indigo-500 focus:outline-none bg-white text-gray-950"
            >
              <option value="">All actions</option>
              <option value="login">login</option>
              <option value="login_failed">login_failed</option>
              <option value="logout">logout</option>
              <option value="upload">upload</option>
              <option value="search">search</option>
              <option value="role_change">role_change</option>
              <option value="disable_user">disable_user</option>
              <option value="enable_user">enable_user</option>
              <option value="submit_feedback">submit_feedback</option>
            </select>
          </div>
        </div>

        {logsLoading ? (
          <p className="text-gray-400">Loading audit logs...</p>
        ) : filteredLogs.length === 0 ? (
          <p className="text-gray-400">No logs found matching your criteria.</p>
        ) : (
          <>
            <div className="bg-white border border-gray-200 rounded-xl overflow-hidden shadow-sm">
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead className="bg-gray-50 border-b border-gray-200">
                    <tr>
                      <th className="text-left px-4 py-3 font-medium text-gray-600">Timestamp</th>
                      <th className="text-left px-4 py-3 font-medium text-gray-600">User Email</th>
                      <th className="text-left px-4 py-3 font-medium text-gray-600">Action</th>
                      <th className="text-left px-4 py-3 font-medium text-gray-600">IP Address</th>
                      <th className="text-left px-4 py-3 font-medium text-gray-600">Resource</th>
                      <th className="text-left px-4 py-3 font-medium text-gray-600">Details</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-100">
                    {filteredLogs.map((log: any) => {
                      const colors = ACTION_COLORS[log.action] || { bg: '#f3f4f6', color: '#374151' }
                      return (
                        <tr key={log.id} className="hover:bg-gray-50">
                          <td className="px-4 py-3 text-gray-500 text-xs">
                            {log.timestamp ? new Date(log.timestamp).toLocaleString() : "-"}
                          </td>
                          <td className="px-4 py-3 text-gray-800 font-medium">{log.user_email || "System"}</td>
                          <td className="px-4 py-3">
                            <span
                              style={{ backgroundColor: colors.bg, color: colors.color }}
                              className="text-xs px-2 py-0.5 rounded-full font-medium"
                            >
                              {log.action}
                            </span>
                          </td>
                          <td className="px-4 py-3 text-gray-500 text-xs font-mono">{log.ip_address || "—"}</td>
                          <td className="px-4 py-3 text-gray-500 text-xs">
                            {log.resource_type ? `${log.resource_type} (${log.resource_id})` : "—"}
                          </td>
                          <td className="px-4 py-3">
                            {log.details ? (
                              <button
                                onClick={() => setSelectedLog(log)}
                                className="text-indigo-600 hover:text-indigo-900 text-xs font-semibold flex items-center gap-1"
                              >
                                <Eye size={13} /> View Details
                              </button>
                            ) : "—"}
                          </td>
                        </tr>
                      )
                    })}
                  </tbody>
                </table>
              </div>
            </div>

            {/* Pagination */}
            <div className="flex gap-3 mt-4 items-center">
              <button
                onClick={() => setLogPage(p => p - 1)}
                disabled={logPage === 0}
                className="px-4 py-2 border border-gray-200 rounded-lg text-sm bg-white font-medium hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                Previous
              </button>
              <span className="text-sm text-gray-500">
                Page {logPage + 1}
              </span>
              <button
                onClick={() => setLogPage(p => p + 1)}
                disabled={auditLogs.length < logLimit}
                className="px-4 py-2 border border-gray-200 rounded-lg text-sm bg-white font-medium hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                Next
              </button>
            </div>
          </>
        )}
      </div>
    )}

    {/* Selected Log details inspection modal */}
    {selectedLog && (
      <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center p-4 z-50">
        <div className="bg-white rounded-xl max-w-lg w-full p-6 relative">
          <h3 className="text-lg font-bold text-gray-900 mb-4">Log Details</h3>
          <div className="bg-gray-50 rounded-lg p-4 font-mono text-xs overflow-auto max-h-96">
            <pre className="whitespace-pre-wrap">{JSON.stringify(selectedLog.details, null, 2)}</pre>
          </div>
          <div className="mt-6 flex justify-end">
            <button
              onClick={() => setSelectedLog(null)}
              className="px-4 py-2 bg-indigo-600 hover:bg-indigo-700 text-white rounded-lg text-sm font-semibold transition-all"
            >
              Close
            </button>
          </div>
        </div>
      </div>
    )}
  </div>
)
}
