import { EditOutlined, PlusOutlined, SafetyCertificateOutlined } from "@ant-design/icons"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { Avatar, Button, Form, Input, Modal, Select, Space, Switch, Table, Tag, message } from "antd"
import { useEffect, useState } from "react"
import { apiRequest } from "../../api/client"
import type { Role, Staff } from "../../api/types"
import { PageHeader } from "../../components/PageHeader"
import { useLanguage } from "../../i18n/LanguageProvider"
import { dateTime } from "../../utils/format"

type StaffForm = { email?: string; role_codes: string[] }

export function StaffPage() {
  const { locale } = useLanguage()
  const client = useQueryClient()
  const [editing, setEditing] = useState<Staff | "new" | null>(null)
  const [form] = Form.useForm<StaffForm>()
  const staff = useQuery({ queryKey: ["staff"], queryFn: () => apiRequest<Staff[]>("/staff") })
  const roles = useQuery({ queryKey: ["roles"], queryFn: () => apiRequest<Role[]>("/roles") })
  useEffect(() => { if (editing === "new") form.setFieldsValue({ email: "", role_codes: [] }); else if (editing) form.setFieldsValue({ role_codes: editing.role_codes }) }, [editing, form])
  const save = useMutation({
    mutationFn: (values: StaffForm) => apiRequest<Staff>(editing === "new" ? "/staff" : `/staff/${editing?.user_id}/roles`, { method: editing === "new" ? "POST" : "PUT", body: JSON.stringify(values) }),
    onSuccess: () => { setEditing(null); void client.invalidateQueries({ queryKey: ["staff"] }); void message.success(locale === "ru" ? "Доступы сохранены" : "Access saved") },
    onError: (error: Error) => void message.error(error.message),
  })
  const toggle = useMutation({
    mutationFn: (row: Staff) => apiRequest<Staff>(`/staff/${row.user_id}/status`, { method: "PATCH", body: JSON.stringify({ is_active: !row.is_active }) }),
    onSuccess: () => void client.invalidateQueries({ queryKey: ["staff"] }),
    onError: (error: Error) => void message.error(error.message),
  })
  const copy = locale === "ru" ? { title: "Сотрудники и роли", description: "Доступ к разделам по принципу минимальных полномочий", invite: "Добавить сотрудника", employee: "Сотрудник", roles: "Роли", mfa: "MFA", last: "Последний вход", active: "Активен", edit: "Права", email: "Email зарегистрированного пользователя", save: "Сохранить" } : { title: "Staff & roles", description: "Least-privilege access to admin sections", invite: "Add staff member", employee: "Employee", roles: "Roles", mfa: "MFA", last: "Last sign in", active: "Active", edit: "Access", email: "Registered user email", save: "Save" }
  return <div className="page-stack">
    <PageHeader title={copy.title} description={copy.description} actions={<Button type="primary" icon={<PlusOutlined />} onClick={() => setEditing("new")}>{copy.invite}</Button>} />
    <Table<Staff> rowKey="user_id" loading={staff.isLoading} dataSource={staff.data} pagination={false} columns={[
      { title: copy.employee, render: (_: unknown, row) => <Space><Avatar>{`${row.name[0] || ""}${row.surname[0] || ""}`}</Avatar><div className="table-primary"><strong>{row.name} {row.surname}</strong><small>{row.email || `ID ${row.user_id}`}</small></div></Space> },
      { title: copy.roles, dataIndex: "role_codes", render: (values: string[]) => <Space wrap>{values.map((value) => <Tag key={value}>{value}</Tag>)}</Space> },
      { title: copy.mfa, dataIndex: "mfa_enabled", render: (value: boolean) => <Tag icon={<SafetyCertificateOutlined />} color={value ? "green" : "orange"}>{value ? "On" : "Setup required"}</Tag> },
      { title: copy.last, dataIndex: "last_login_at", render: (value: string | null) => dateTime(value, locale) },
      { title: copy.active, dataIndex: "is_active", render: (value: boolean, row) => <Switch checked={value} loading={toggle.isPending} onChange={() => toggle.mutate(row)} /> },
      { title: "", align: "right", render: (_: unknown, row) => <Button icon={<EditOutlined />} onClick={() => setEditing(row)}>{copy.edit}</Button> },
    ]} />
    <Modal open={Boolean(editing)} title={editing === "new" ? copy.invite : copy.edit} okText={copy.save} confirmLoading={save.isPending} onCancel={() => setEditing(null)} onOk={() => void form.validateFields().then((values) => save.mutate(values))}>
      <Form form={form} layout="vertical">{editing === "new" ? <Form.Item name="email" label={copy.email} rules={[{ required: true, type: "email" }]}><Input /></Form.Item> : null}<Form.Item name="role_codes" label={copy.roles} rules={[{ required: true }]}><Select mode="multiple" options={(roles.data || []).map((role) => ({ value: role.code, label: locale === "ru" ? role.name_ru : role.name_en }))} /></Form.Item></Form>
    </Modal>
  </div>
}
