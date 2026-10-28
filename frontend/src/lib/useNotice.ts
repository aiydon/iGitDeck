import { useCallback, useState } from "react";

import type { NoticeTone } from "../components/Notice";
import { errorMessage } from "./format";

export interface NoticeState {
  tone: NoticeTone;
  message: string;
}

export interface NoticeController {
  notice: NoticeState | null;
  show: (message: string, tone?: NoticeTone) => void;
  fail: (error: unknown) => void;
  dismiss: () => void;
}

/** One transient banner per page; pages only describe what happened. */
export function useNotice(): NoticeController {
  const [notice, setNotice] = useState<NoticeState | null>(null);

  const show = useCallback(
    (message: string, tone: NoticeTone = "info") => setNotice({ tone, message }),
    [],
  );
  const fail = useCallback(
    (error: unknown) => setNotice({ tone: "error", message: errorMessage(error) }),
    [],
  );
  const dismiss = useCallback(() => setNotice(null), []);

  return { notice, show, fail, dismiss };
}
