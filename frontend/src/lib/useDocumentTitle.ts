import { useEffect } from "react";

/** Each page owns the document title, so only one effect ever writes it. */
export function useDocumentTitle(title: string | null | undefined): void {
  useEffect(() => {
    if (title) document.title = title;
  }, [title]);
}
