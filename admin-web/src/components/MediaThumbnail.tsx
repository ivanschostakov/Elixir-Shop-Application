import { FileImageOutlined } from "@ant-design/icons"
import { Image } from "antd"
import { useState } from "react"
import { useLanguage } from "../i18n/LanguageProvider"
import { resolveAdminMediaUrl } from "../utils/media"

export function MediaThumbnail({ src, size, height = size, alt }: {
  src?: string | null; size: number; height?: number; alt: string
}) {
  const { locale } = useLanguage()
  const url = resolveAdminMediaUrl(src)
  const [failedUrl, setFailedUrl] = useState<string>()
  return url && failedUrl !== url
    ? <Image src={url} alt={alt} width={size} height={height} style={{ objectFit: "contain" }} onError={() => setFailedUrl(url)} />
    : <span className="media-unavailable" style={{ width: size, height }} role="img" aria-label={alt}>
        <FileImageOutlined />{locale === "ru" ? "Нет изображения" : "No image"}
      </span>
}
