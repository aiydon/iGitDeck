import { useState } from "react";
import type { FormEvent } from "react";

import { api } from "../api/client";
import type { RepoAddResult } from "../api/client";
import { errorMessage } from "../lib/format";
import { Modal } from "./Modal";
import { Spinner } from "./Spinner";

interface AddRepoDialogProps {
  onClose: () => void;
  onAdded: (result: RepoAddResult) => void;
}

export function AddRepoDialog({ onClose, onAdded }: AddRepoDialogProps) {
  const [url, setUrl] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const trimmed = url.trim();
    if (!trimmed) {
      setError("请输入仓库地址");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const result = await api.addRepo(trimmed);
      onAdded(result);
    } catch (cause) {
      setError(errorMessage(cause));
    } finally {
      setBusy(false);
    }
  }

  return (
    <Modal
      title="添加仓库"
      subtitle="加入同步队列后，后台会自动 clone、统计并建立索引。"
      onClose={onClose}
      width={520}
    >
      <form className="form-stack" onSubmit={handleSubmit}>
        <label className="field">
          <span>仓库地址</span>
          <input
            autoFocus
            value={url}
            onChange={(event) => setUrl(event.target.value)}
            placeholder="https://github.com/owner/repo"
            spellCheck={false}
            autoCapitalize="none"
            disabled={busy}
          />
        </label>
        <p className="field-hint">
          支持 GitHub / GitLab / Gitee / Bitbucket 的 HTTPS、SSH 地址，或
          <code>owner/repo</code> 简写。
        </p>
        {error && <div className="form-error">{error}</div>}
        <footer className="modal-actions">
          <button type="button" className="button ghost" onClick={onClose}>
            取消
          </button>
          <button type="submit" className="button primary" disabled={busy}>
            {busy && <Spinner />}
            {busy ? "正在添加" : "加入同步"}
          </button>
        </footer>
      </form>
    </Modal>
  );
}
