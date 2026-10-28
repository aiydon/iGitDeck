import { useState } from "react";
import type { FormEvent } from "react";

import { api } from "../api/client";
import type { RepoBatchResult } from "../api/client";
import { errorMessage } from "../lib/format";
import { Modal } from "./Modal";
import { Spinner } from "./Spinner";

const MAX_URLS = 200;

interface AddRepoDialogProps {
  onClose: () => void;
  onDone: (result: RepoBatchResult) => void;
}

export function AddRepoDialog({ onClose, onDone }: AddRepoDialogProps) {
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<RepoBatchResult | null>(null);

  const urls = text
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter(Boolean);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (urls.length === 0) {
      setError("请至少输入一个仓库地址");
      return;
    }
    if (urls.length > MAX_URLS) {
      setError(`一次最多添加 ${MAX_URLS} 个仓库`);
      return;
    }
    setBusy(true);
    setError(null);
    try {
      setResult(await api.addRepos(urls));
    } catch (cause) {
      setError(errorMessage(cause));
    } finally {
      setBusy(false);
    }
  }

  const failures = result?.items.filter((item) => item.error) ?? [];

  return (
    <Modal
      title="添加仓库"
      subtitle="每行一个地址，可一次加入多个仓库。加入后由后台依次 clone、统计并建立索引。"
      onClose={onClose}
      width={560}
    >
      {result ? (
        <div className="form-stack">
          <div className="batch-summary">
            <span className="batch-count success">新增 {result.created}</span>
            <span>已存在 {result.existing}</span>
            <span className={result.failed ? "danger-text" : "muted"}>
              失败 {result.failed}
            </span>
          </div>
          {failures.length > 0 && (
            <ul className="batch-errors">
              {failures.map((item, index) => (
                <li key={`${item.url}-${index}`}>
                  <code>{item.url}</code>
                  <span>{item.error}</span>
                </li>
              ))}
            </ul>
          )}
          <footer className="modal-actions">
            <button type="button" className="button primary" onClick={() => onDone(result)}>
              完成
            </button>
          </footer>
        </div>
      ) : (
        <form className="form-stack" onSubmit={handleSubmit}>
          <label className="field">
            <span>仓库地址</span>
            <textarea
              autoFocus
              value={text}
              onChange={(event) => setText(event.target.value)}
              placeholder={"https://github.com/owner/repo\ngit@github.com:owner/repo.git\nowner/repo"}
              rows={8}
              spellCheck={false}
              autoCapitalize="none"
              disabled={busy}
            />
          </label>
          <p className="field-hint">
            支持 GitHub / GitLab / Gitee / Bitbucket 的 HTTPS、SSH 地址及
            <code>owner/repo</code> 简写；空行会被忽略，单次最多 {MAX_URLS} 个。
            <span className="batch-count-hint">
              {urls.length > 0 ? `已识别 ${urls.length} 个地址` : "一行一个地址"}
            </span>
          </p>
          {error && <div className="form-error">{error}</div>}
          <footer className="modal-actions">
            <button type="button" className="button ghost" onClick={onClose}>
              取消
            </button>
            <button type="submit" className="button primary" disabled={busy || urls.length === 0}>
              {busy && <Spinner />}
              {busy ? "正在添加" : `加入同步${urls.length > 1 ? `（${urls.length}）` : ""}`}
            </button>
          </footer>
        </form>
      )}
    </Modal>
  );
}
