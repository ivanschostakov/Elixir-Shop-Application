import { Calendar, CalendarList, type CalendarProps, type CalendarListProps } from "react-native-calendars"

type Props = ({ paged?: false } & CalendarProps) | ({ paged: true } & CalendarListProps)
/** Shared date renderer; callers retain their single-date/range selection rules and locale. */
export function AppCalendar(props: Props) {
    if (props.paged) {
        const { paged: _paged, ...rest } = props
        return <CalendarList {...rest} />
    }
    const { paged: _paged, ...rest } = props
    return <Calendar {...rest} />
}
