import { BookOutlined } from "@ant-design/icons"
import { Alert, Button, Modal, Space, Table, Tag, Typography } from "antd"
import { useState } from "react"
import type { Locale } from "../api/types"
import { INTERNAL_APP_LINK_GUIDE, type InternalAppLinkGuideEntry } from "../utils/internalLinks"

type InternalLinkGuideProps = {
  locale: Locale
  onSelect?: (path: string) => void
  buttonType?: "link" | "default"
}

const accessColors = { public: "green", account: "blue", context: "orange" }

export function InternalLinkGuide({ locale, onSelect, buttonType = "link" }: InternalLinkGuideProps) {
  const [open, setOpen] = useState(false)
  const copy = locale === "ru"
    ? {
      button: "Открыть полный справочник страниц и параметров",
      title: "Внутренние ссылки приложения",
      intro: "Выберите готовый пример или соберите путь по таблице. Ссылка начинается с одного /, без домена. Для баннера укажите либо внутреннюю, либо внешнюю ссылку.",
      page: "Экран",
      path: "Путь",
      parameters: "Параметры и дополнения",
      example: "Готовый пример",
      access: "Доступ",
      public: "Для всех",
      account: "Нужен вход",
      context: "Нужен контекст",
      use: "Использовать",
      contextWarning: "Ссылки на оформление, доставку и оплату зависят от корзины, черновика или заказа конкретного клиента. Не вставляйте один orderId или draftId в массовую рассылку.",
    }
    : {
      button: "Open the full page and parameter guide",
      title: "Internal app links",
      intro: "Choose a ready example or build a path from the table. Links begin with a single / and contain no domain. For banners, set either an internal or external link.",
      page: "Screen",
      path: "Path",
      parameters: "Parameters and options",
      example: "Ready example",
      access: "Access",
      public: "Public",
      account: "Login required",
      context: "Context required",
      use: "Use",
      contextWarning: "Checkout, delivery and payment links depend on a specific customer's basket, draft or order. Do not place one orderId or draftId in a mass campaign.",
    }

  return (
    <>
      <Button type={buttonType} size="small" icon={<BookOutlined />} onClick={() => setOpen(true)}>
        {copy.button}
      </Button>
      <Modal
        width={1180}
        open={open}
        title={copy.title}
        footer={null}
        onCancel={() => setOpen(false)}
        styles={{ body: { maxHeight: "calc(100vh - 180px)", overflowY: "auto" } }}
      >
        <Space direction="vertical" size={12} style={{ width: "100%" }}>
          <Alert type="info" showIcon message={copy.intro} />
          <Alert type="warning" showIcon message={copy.contextWarning} />
          <Table<InternalAppLinkGuideEntry>
            rowKey="key"
            size="small"
            pagination={false}
            dataSource={INTERNAL_APP_LINK_GUIDE}
            scroll={{ x: 1050 }}
            columns={[
              {
                title: copy.page,
                dataIndex: "page",
                width: 170,
                fixed: "left",
                render: (value: InternalAppLinkGuideEntry["page"], row) => (
                  <Space direction="vertical" size={0}>
                    <Typography.Text strong>{value[locale]}</Typography.Text>
                    {row.note ? <Typography.Text type="secondary">{row.note[locale]}</Typography.Text> : null}
                  </Space>
                ),
              },
              {
                title: copy.path,
                dataIndex: "path",
                width: 190,
                render: (value: string) => <Typography.Text code copyable>{value}</Typography.Text>,
              },
              {
                title: copy.parameters,
                dataIndex: "parameters",
                width: 310,
                render: (value: InternalAppLinkGuideEntry["parameters"]) => value[locale],
              },
              {
                title: copy.example,
                dataIndex: "example",
                width: 270,
                render: (value: string) => <Typography.Text code copyable>{value}</Typography.Text>,
              },
              {
                title: copy.access,
                dataIndex: "access",
                width: 130,
                render: (value: InternalAppLinkGuideEntry["access"]) => (
                  <Tag color={accessColors[value]}>{copy[value]}</Tag>
                ),
              },
              ...(onSelect ? [{
                title: "",
                width: 120,
                fixed: "right" as const,
                render: (_value: unknown, row: InternalAppLinkGuideEntry) => (
                  <Button
                    size="small"
                    onClick={() => {
                      onSelect(row.example)
                      setOpen(false)
                    }}
                  >
                    {copy.use}
                  </Button>
                ),
              }] : []),
            ]}
          />
        </Space>
      </Modal>
    </>
  )
}
