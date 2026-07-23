import {
  DeleteOutlined,
  EditOutlined,
  MailOutlined,
  PlusOutlined,
  ReloadOutlined,
  SafetyCertificateOutlined,
  StopOutlined,
} from "@ant-design/icons"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import {
  Alert,
  Avatar,
  Button,
  Card,
  Checkbox,
  Collapse,
  Form,
  Input,
  Modal,
  Popconfirm,
  Select,
  Space,
  Switch,
  Table,
  Tag,
  Typography,
  message,
} from "antd"
import { useEffect, useMemo, useState } from "react"
import { apiRequest } from "../../api/client"
import type { AdminInvitation, Role, Staff } from "../../api/types"
import { useAuth } from "../../auth/AuthProvider"
import { PageHeader } from "../../components/PageHeader"
import { useLanguage } from "../../i18n/LanguageProvider"
import { dateTime } from "../../utils/format"

type InviteForm = { email: string; role_codes: string[]; confirm_superadmin?: boolean }
type RoleForm = { role_codes: string[]; confirm_superadmin?: boolean }

const statusColors: Record<AdminInvitation["status"], string> = {
  pending: "blue",
  accepted: "green",
  expired: "orange",
  revoked: "default",
}

export function StaffPage() {
  const { locale } = useLanguage()
  const { principal } = useAuth()
  const client = useQueryClient()
  const [inviteOpen, setInviteOpen] = useState(false)
  const [editing, setEditing] = useState<Staff | null>(null)
  const [inviteForm] = Form.useForm<InviteForm>()
  const [roleForm] = Form.useForm<RoleForm>()
  const inviteRoles = Form.useWatch("role_codes", inviteForm) || []
  const editedRoles = Form.useWatch("role_codes", roleForm) || []

  const staff = useQuery({ queryKey: ["staff"], queryFn: () => apiRequest<Staff[]>("/staff") })
  const roles = useQuery({ queryKey: ["roles"], queryFn: () => apiRequest<Role[]>("/roles") })
  const invitations = useQuery({
    queryKey: ["staff-invitations"],
    queryFn: () => apiRequest<AdminInvitation[]>("/staff/invitations"),
  })

  const roleByCode = useMemo(
    () => new Map((roles.data || []).map((role) => [role.code, role])),
    [roles.data],
  )
  const roleName = (code: string) => {
    const role = roleByCode.get(code)
    return role ? (locale === "ru" ? role.name_ru : role.name_en) : code
  }
  const roleOptions = (roles.data || []).map((role) => ({
    value: role.code,
    label: locale === "ru" ? role.name_ru : role.name_en,
  }))

  useEffect(() => {
    if (editing) roleForm.setFieldsValue({ role_codes: editing.role_codes, confirm_superadmin: false })
  }, [editing, roleForm])

  const refreshAll = () => {
    void client.invalidateQueries({ queryKey: ["staff"] })
    void client.invalidateQueries({ queryKey: ["staff-invitations"] })
  }

  const invite = useMutation({
    mutationFn: (values: InviteForm) => apiRequest<AdminInvitation>("/staff/invitations", {
      method: "POST",
      body: JSON.stringify(values),
    }),
    onSuccess: () => {
      setInviteOpen(false)
      inviteForm.resetFields()
      refreshAll()
      void message.success(locale === "ru" ? "Приглашение отправлено" : "Invitation sent")
    },
    onError: (error: Error) => void message.error(error.message),
  })
  const saveRoles = useMutation({
    mutationFn: (values: RoleForm) => apiRequest<Staff>(`/staff/${editing?.user_id}/roles`, {
      method: "PUT",
      body: JSON.stringify(values),
    }),
    onSuccess: () => {
      setEditing(null)
      refreshAll()
      void message.success(locale === "ru" ? "Роли обновлены" : "Roles updated")
    },
    onError: (error: Error) => void message.error(error.message),
  })
  const toggle = useMutation({
    mutationFn: (row: Staff) => apiRequest<Staff>(`/staff/${row.user_id}/status`, {
      method: "PATCH",
      body: JSON.stringify({ is_active: !row.is_active }),
    }),
    onSuccess: refreshAll,
    onError: (error: Error) => void message.error(error.message),
  })
  const remove = useMutation({
    mutationFn: (row: Staff) => apiRequest<void>(`/staff/${row.user_id}`, { method: "DELETE" }),
    onSuccess: () => {
      refreshAll()
      void message.success(locale === "ru" ? "Доступ сотрудника удалён" : "Staff access removed")
    },
    onError: (error: Error) => void message.error(error.message),
  })
  const resend = useMutation({
    mutationFn: (row: AdminInvitation) => apiRequest<AdminInvitation>(`/staff/invitations/${row.id}/resend`, { method: "POST" }),
    onSuccess: () => {
      refreshAll()
      void message.success(locale === "ru" ? "Новая ссылка отправлена" : "A new link was sent")
    },
    onError: (error: Error) => void message.error(error.message),
  })
  const revoke = useMutation({
    mutationFn: (row: AdminInvitation) => apiRequest<AdminInvitation>(`/staff/invitations/${row.id}/revoke`, { method: "POST" }),
    onSuccess: () => {
      refreshAll()
      void message.success(locale === "ru" ? "Приглашение отозвано" : "Invitation revoked")
    },
    onError: (error: Error) => void message.error(error.message),
  })

  const copy = locale === "ru"
    ? {
        title: "Сотрудники и роли",
        description: "Приглашения по email, комбинируемые роли, MFA и полный аудит изменений доступа",
        invite: "Пригласить сотрудника",
        model: "Модель доступа",
        modelText: "Выберите минимальный набор ролей по обязанностям. Права суммируются. Суперадминистратор назначается отдельно и получает полный доступ.",
        team: "Действующие сотрудники",
        invitations: "История приглашений",
        employee: "Сотрудник",
        roles: "Роли",
        mfa: "MFA",
        last: "Последний вход",
        active: "Активен",
        edit: "Изменить роли",
        email: "Рабочий email",
        send: "Отправить приглашение",
        save: "Сохранить",
        invitedBy: "Пригласил",
        status: "Статус",
        dates: "Отправлено / срок",
        actions: "Действия",
        resend: "Отправить новую ссылку",
        revoke: "Отозвать",
        revokeConfirm: "Отозвать это приглашение?",
        remove: "Удалить",
        removeConfirm: "Удалить доступ сотрудника к админке?",
        removeDescription: "Все админ-сессии завершатся, роли и MFA будут удалены. Клиентский профиль и история действий сохранятся.",
        superConfirm: "Я понимаю, что эта роль дает полный доступ, включая управление сотрудниками и аудитом.",
        pending: "Ожидает",
        accepted: "Принято",
        expired: "Истекло",
        revoked: "Отозвано",
      }
    : {
        title: "Staff & roles",
        description: "Email invitations, composable roles, MFA, and a complete access audit trail",
        invite: "Invite staff member",
        model: "Access model",
        modelText: "Assign the smallest role set needed for the job. Permissions are combined. Super administrator is assigned alone and grants full access.",
        team: "Active staff",
        invitations: "Invitation history",
        employee: "Employee",
        roles: "Roles",
        mfa: "MFA",
        last: "Last sign in",
        active: "Active",
        edit: "Edit roles",
        email: "Work email",
        send: "Send invitation",
        save: "Save",
        invitedBy: "Invited by",
        status: "Status",
        dates: "Sent / expires",
        actions: "Actions",
        resend: "Send a new link",
        revoke: "Revoke",
        revokeConfirm: "Revoke this invitation?",
        remove: "Remove",
        removeConfirm: "Remove this staff member's admin access?",
        removeDescription: "All admin sessions will end and roles and MFA will be removed. The customer profile and activity history will remain.",
        superConfirm: "I understand that this role grants full access, including staff and audit management.",
        pending: "Pending",
        accepted: "Accepted",
        expired: "Expired",
        revoked: "Revoked",
      }
  const statusText = (value: AdminInvitation["status"]) => copy[value]

  return (
    <div className="page-stack">
      <PageHeader
        title={copy.title}
        description={copy.description}
        actions={<Button type="primary" icon={<PlusOutlined />} onClick={() => setInviteOpen(true)}>{copy.invite}</Button>}
      />

      <Alert type="info" showIcon message={copy.model} description={copy.modelText} />
      <Collapse
        items={[{
          key: "roles",
          label: copy.model,
          children: (
            <div className="role-catalog-grid">
              {(roles.data || []).map((role) => (
                <Card size="small" key={role.code}>
                  <Typography.Text strong>{locale === "ru" ? role.name_ru : role.name_en}</Typography.Text>
                  <Typography.Paragraph type="secondary">
                    {locale === "ru" ? role.description_ru : role.description_en}
                  </Typography.Paragraph>
                  <Tag>{role.permissions.includes("*") ? (locale === "ru" ? "Все права" : "All permissions") : `${role.permissions.length} permissions`}</Tag>
                </Card>
              ))}
            </div>
          ),
        }]}
      />

      <Card title={copy.team}>
        <Table<Staff>
          rowKey="user_id"
          loading={staff.isLoading}
          dataSource={staff.data}
          pagination={false}
          scroll={{ x: 900 }}
          columns={[
            {
              title: copy.employee,
              render: (_: unknown, row) => (
                <Space>
                  <Avatar>{`${row.name[0] || ""}${row.surname[0] || ""}`}</Avatar>
                  <div className="table-primary">
                    <strong>{row.name} {row.surname}</strong>
                    <small>{row.email || `ID ${row.user_id}`}</small>
                  </div>
                </Space>
              ),
            },
            {
              title: copy.roles,
              dataIndex: "role_codes",
              render: (values: string[]) => <Space wrap>{values.map((value) => <Tag key={value}>{roleName(value)}</Tag>)}</Space>,
            },
            {
              title: copy.mfa,
              dataIndex: "mfa_enabled",
              render: (value: boolean) => (
                <Tag icon={<SafetyCertificateOutlined />} color={value ? "green" : "orange"}>
                  {value ? "On" : "Setup required"}
                </Tag>
              ),
            },
            { title: copy.last, dataIndex: "last_login_at", render: (value: string | null) => dateTime(value, locale) },
            {
              title: copy.active,
              dataIndex: "is_active",
              render: (value: boolean, row) => <Switch checked={value} loading={toggle.isPending} onChange={() => toggle.mutate(row)} />,
            },
            {
              title: "",
              align: "right",
              render: (_: unknown, row) => (
                <Space>
                  <Button icon={<EditOutlined />} onClick={() => setEditing(row)}>{copy.edit}</Button>
                  {row.user_id !== principal?.user.id ? (
                    <Popconfirm
                      title={copy.removeConfirm}
                      description={copy.removeDescription}
                      okText={copy.remove}
                      okButtonProps={{ danger: true, loading: remove.isPending }}
                      onConfirm={() => remove.mutateAsync(row)}
                    >
                      <Button danger icon={<DeleteOutlined />}>{copy.remove}</Button>
                    </Popconfirm>
                  ) : null}
                </Space>
              ),
            },
          ]}
        />
      </Card>

      <Card title={copy.invitations}>
        <Table<AdminInvitation>
          rowKey="id"
          loading={invitations.isLoading}
          dataSource={invitations.data}
          pagination={{ pageSize: 10, hideOnSinglePage: true }}
          scroll={{ x: 900 }}
          columns={[
            {
              title: copy.email,
              dataIndex: "email",
              render: (value: string, row) => (
                <div className="table-primary">
                  <strong>{value}</strong>
                  <small>{row.role_codes.map(roleName).join(", ")}</small>
                </div>
              ),
            },
            { title: copy.invitedBy, dataIndex: "invited_by_name" },
            {
              title: copy.status,
              dataIndex: "status",
              render: (value: AdminInvitation["status"]) => <Tag color={statusColors[value]}>{statusText(value)}</Tag>,
            },
            {
              title: copy.dates,
              render: (_: unknown, row) => (
                <div className="table-primary">
                  <strong>{dateTime(row.last_sent_at, locale)}</strong>
                  <small>{dateTime(row.expires_at, locale)} · #{row.send_count}</small>
                </div>
              ),
            },
            {
              title: copy.actions,
              align: "right",
              render: (_: unknown, row) => row.status === "pending" || row.status === "expired" ? (
                <Space>
                  <Button icon={<ReloadOutlined />} loading={resend.isPending} onClick={() => resend.mutate(row)}>{copy.resend}</Button>
                  {row.status === "pending" ? (
                    <Popconfirm title={copy.revokeConfirm} onConfirm={() => revoke.mutate(row)}>
                      <Button danger icon={<StopOutlined />} loading={revoke.isPending}>{copy.revoke}</Button>
                    </Popconfirm>
                  ) : null}
                </Space>
              ) : null,
            },
          ]}
        />
      </Card>

      <Modal
        open={inviteOpen}
        title={copy.invite}
        okText={copy.send}
        confirmLoading={invite.isPending}
        onCancel={() => { setInviteOpen(false); inviteForm.resetFields() }}
        onOk={() => void inviteForm.validateFields().then((values) => invite.mutate(values))}
      >
        <Form form={inviteForm} layout="vertical" initialValues={{ role_codes: [] }}>
          <Form.Item name="email" label={copy.email} rules={[{ required: true, type: "email" }]}>
            <Input prefix={<MailOutlined />} autoComplete="email" />
          </Form.Item>
          <Form.Item name="role_codes" label={copy.roles} rules={[{ required: true }]}>
            <Select
              mode="multiple"
              options={roleOptions}
              onChange={(values) => {
                if (values.includes("superadmin")) inviteForm.setFieldValue("role_codes", ["superadmin"])
              }}
            />
          </Form.Item>
          {inviteRoles.includes("superadmin") ? (
            <Form.Item name="confirm_superadmin" valuePropName="checked" rules={[{ validator: (_, value) => value ? Promise.resolve() : Promise.reject(new Error(copy.superConfirm)) }]}>
              <Checkbox>{copy.superConfirm}</Checkbox>
            </Form.Item>
          ) : null}
        </Form>
      </Modal>

      <Modal
        open={Boolean(editing)}
        title={copy.edit}
        okText={copy.save}
        confirmLoading={saveRoles.isPending}
        onCancel={() => setEditing(null)}
        onOk={() => void roleForm.validateFields().then((values) => saveRoles.mutate(values))}
      >
        <Form form={roleForm} layout="vertical">
          <Form.Item name="role_codes" label={copy.roles} rules={[{ required: true }]}>
            <Select
              mode="multiple"
              options={roleOptions}
              onChange={(values) => {
                if (values.includes("superadmin")) roleForm.setFieldValue("role_codes", ["superadmin"])
              }}
            />
          </Form.Item>
          {editedRoles.includes("superadmin") && !editing?.role_codes.includes("superadmin") ? (
            <Form.Item name="confirm_superadmin" valuePropName="checked" rules={[{ validator: (_, value) => value ? Promise.resolve() : Promise.reject(new Error(copy.superConfirm)) }]}>
              <Checkbox>{copy.superConfirm}</Checkbox>
            </Form.Item>
          ) : null}
        </Form>
      </Modal>
    </div>
  )
}
