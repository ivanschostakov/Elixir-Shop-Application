import { DatePicker } from "antd"
import dayjs from "dayjs"

// Keep the existing local-time form payload; only change the display/input format.
export function LocalDateTimeInput({ value, onChange, id }: {
  value?: string | null; onChange?: (value: string | null) => void; id?: string
}) {
  return <DatePicker id={id} showTime format="DD.MM.YYYY HH:mm" style={{ width: "100%" }}
    value={value && dayjs(value).isValid() ? dayjs(value) : null}
    onChange={next => onChange?.(next ? next.format("YYYY-MM-DDTHH:mm") : null)} />
}
