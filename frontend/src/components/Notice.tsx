import { useEffect, useRef } from "react";

import { AlertIcon, CheckIcon, CloseIcon, InfoIcon } from "./icons";

export type NoticeTone = "success" | "error" | "info";

interface NoticeProps {
  message: string;
  tone?: NoticeTone;
  onClose: () => void;
}

export function Notice({ message, tone = "info", onClose }: NoticeProps) {
  const closeRef = useRef(onClose);
  closeRef.current = onClose;

  useEffect(() => {
    const timer = window.setTimeout(() => closeRef.current(), tone === "error" ? 8000 : 4500);
    return () => window.clearTimeout(timer);
  }, [message, tone]);

  const Icon = tone === "success" ? CheckIcon : tone === "error" ? AlertIcon : InfoIcon;
  return (
    <div className={`notice notice-${tone}`} role="status">
      <Icon size={17} />
      <span>{message}</span>
      <button type="button" className="notice-close" onClick={onClose} aria-label="关闭提示">
        <CloseIcon size={15} />
      </button>
    </div>
  );
}
