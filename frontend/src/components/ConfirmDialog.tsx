import type { ReactNode } from "react";

import { AlertIcon } from "./icons";
import { Modal } from "./Modal";
import { Spinner } from "./Spinner";

interface ConfirmDialogProps {
  title: string;
  message: ReactNode;
  confirmLabel: string;
  busy?: boolean;
  onConfirm: () => void;
  onClose: () => void;
}

export function ConfirmDialog({
  title,
  message,
  confirmLabel,
  busy = false,
  onConfirm,
  onClose,
}: ConfirmDialogProps) {
  return (
    <Modal title={title} onClose={busy ? () => undefined : onClose} width={460}>
      <div className="confirm-body">
        <div className="confirm-icon">
          <AlertIcon size={22} />
        </div>
        <div className="confirm-text">{message}</div>
      </div>
      <footer className="modal-actions">
        <button type="button" className="button ghost" onClick={onClose} disabled={busy}>
          取消
        </button>
        <button type="button" className="button danger" onClick={onConfirm} disabled={busy}>
          {busy && <Spinner />}
          {confirmLabel}
        </button>
      </footer>
    </Modal>
  );
}
