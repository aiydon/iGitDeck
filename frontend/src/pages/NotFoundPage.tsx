import { Link } from "react-router-dom";

import { RepoIcon } from "../components/icons";

export function NotFoundPage() {
  return (
    <div className="empty-state not-found">
      <div className="empty-icon">
        <RepoIcon size={30} />
      </div>
      <h1>页面不存在</h1>
      <p>这个地址没有对应的看板页面。</p>
      <div className="empty-action">
        <Link className="button primary" to="/">
          返回仪表盘
        </Link>
      </div>
    </div>
  );
}
