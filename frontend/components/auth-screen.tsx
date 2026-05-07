"use client";

import React, { useState } from "react";
import { ArrowRight, Loader2, LockKeyhole, Mail, UserRound } from "lucide-react";
import { authClient } from "@/lib/auth-client";

interface AuthScreenProps {
  onAuthenticated: () => Promise<void> | void;
}

type AuthMode = "sign-in" | "sign-up";

function getErrorMessage(error: unknown): string {
  if (!error) return "操作失败，请稍后重试";
  if (typeof error === "string") return error;
  if (typeof error === "object" && "message" in error) {
    return String((error as { message?: unknown }).message || "操作失败，请稍后重试");
  }
  return "操作失败，请稍后重试";
}

export default function AuthScreen({ onAuthenticated }: AuthScreenProps) {
  const [mode, setMode] = useState<AuthMode>("sign-in");
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);

  const isSignUp = mode === "sign-up";
  const canSubmit = email.trim() && password.length >= 8 && (!isSignUp || name.trim());

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!canSubmit || isSubmitting) return;

    setError("");
    setIsSubmitting(true);
    try {
      const result = isSignUp
        ? await authClient.signUp.email({
            name: name.trim(),
            email: email.trim(),
            password,
          })
        : await authClient.signIn.email({
            email: email.trim(),
            password,
          });

      if (result.error) {
        setError(getErrorMessage(result.error));
        return;
      }
      await onAuthenticated();
    } catch (err) {
      setError(getErrorMessage(err));
    } finally {
      setIsSubmitting(false);
    }
  };

  const toggleMode = () => {
    setMode((current) => (current === "sign-in" ? "sign-up" : "sign-in"));
    setError("");
  };

  return (
    <main className="min-h-screen bg-[#f4f5f2] text-text-primary">
      <div className="mx-auto grid min-h-screen max-w-6xl grid-cols-1 lg:grid-cols-[0.9fr_1.1fr]">
        <section className="hidden border-r border-[#d9ded4] bg-[#eef1e9] px-10 py-12 lg:flex lg:flex-col lg:justify-between">
          <div>
            <div className="mb-14 flex items-center gap-3">
              <div className="flex h-9 w-9 items-center justify-center rounded-full bg-[#243d37] text-sm font-semibold text-white">
                W
              </div>
              <span className="text-[15px] font-semibold">你的AI外贸业务员</span>
            </div>
            <div className="space-y-6">
              <p className="max-w-sm text-[38px] font-semibold leading-tight tracking-normal text-[#20302d]">
                外贸开发工作台
              </p>
              <p className="max-w-sm text-[15px] leading-7 text-[#63706b]">
                登录后继续管理公司画像、客户名单、开发信和批量发送记录。
              </p>
            </div>
          </div>
          <div className="grid grid-cols-2 gap-3 text-[12px] text-[#66736d]">
            <div className="border-t border-[#cfd6ca] pt-3">客户搜索</div>
            <div className="border-t border-[#cfd6ca] pt-3">开发信撰写</div>
            <div className="border-t border-[#cfd6ca] pt-3">批量发送</div>
            <div className="border-t border-[#cfd6ca] pt-3">投递追踪</div>
          </div>
        </section>

        <section className="flex items-center justify-center px-5 py-10">
          <div className="w-full max-w-[420px]">
            <div className="mb-7 lg:hidden">
              <div className="mb-5 flex items-center gap-3">
                <div className="flex h-9 w-9 items-center justify-center rounded-full bg-[#243d37] text-sm font-semibold text-white">
                  W
                </div>
                <span className="text-[15px] font-semibold">你的AI外贸业务员</span>
              </div>
              <h1 className="text-[30px] font-semibold leading-tight tracking-normal">
                外贸开发工作台
              </h1>
            </div>

            <div className="mb-6 flex rounded-lg bg-[#e7ebe1] p-1">
              <button
                type="button"
                onClick={() => setMode("sign-in")}
                className={`h-9 flex-1 rounded-md text-[14px] font-medium transition-colors ${
                  !isSignUp ? "bg-white text-[#20302d] shadow-sm" : "text-[#69746f]"
                }`}
              >
                登录
              </button>
              <button
                type="button"
                onClick={() => setMode("sign-up")}
                className={`h-9 flex-1 rounded-md text-[14px] font-medium transition-colors ${
                  isSignUp ? "bg-white text-[#20302d] shadow-sm" : "text-[#69746f]"
                }`}
              >
                注册
              </button>
            </div>

            <form onSubmit={handleSubmit} className="space-y-4">
              {isSignUp && (
                <label className="block">
                  <span className="mb-1.5 block text-[13px] font-medium text-[#4e5b56]">
                    姓名
                  </span>
                  <div className="relative">
                    <UserRound
                      size={17}
                      className="absolute left-3 top-1/2 -translate-y-1/2 text-[#79857f]"
                    />
                    <input
                      value={name}
                      onChange={(event) => setName(event.target.value)}
                      autoComplete="name"
                      className="h-11 w-full rounded-lg border border-[#cbd3c6] bg-white pl-10 pr-3 text-[14px] outline-none transition focus:border-[#2f5b50] focus:ring-2 focus:ring-[#2f5b50]/15"
                    />
                  </div>
                </label>
              )}

              <label className="block">
                <span className="mb-1.5 block text-[13px] font-medium text-[#4e5b56]">
                  邮箱
                </span>
                <div className="relative">
                  <Mail
                    size={17}
                    className="absolute left-3 top-1/2 -translate-y-1/2 text-[#79857f]"
                  />
                  <input
                    value={email}
                    onChange={(event) => setEmail(event.target.value)}
                    type="email"
                    autoComplete="email"
                    className="h-11 w-full rounded-lg border border-[#cbd3c6] bg-white pl-10 pr-3 text-[14px] outline-none transition focus:border-[#2f5b50] focus:ring-2 focus:ring-[#2f5b50]/15"
                  />
                </div>
              </label>

              <label className="block">
                <span className="mb-1.5 block text-[13px] font-medium text-[#4e5b56]">
                  密码
                </span>
                <div className="relative">
                  <LockKeyhole
                    size={17}
                    className="absolute left-3 top-1/2 -translate-y-1/2 text-[#79857f]"
                  />
                  <input
                    value={password}
                    onChange={(event) => setPassword(event.target.value)}
                    type="password"
                    autoComplete={isSignUp ? "new-password" : "current-password"}
                    className="h-11 w-full rounded-lg border border-[#cbd3c6] bg-white pl-10 pr-3 text-[14px] outline-none transition focus:border-[#2f5b50] focus:ring-2 focus:ring-[#2f5b50]/15"
                  />
                </div>
              </label>

              {error && (
                <div className="rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-[13px] text-red-700">
                  {error}
                </div>
              )}

              <button
                type="submit"
                disabled={!canSubmit || isSubmitting}
                className="flex h-11 w-full items-center justify-center gap-2 rounded-lg bg-[#243d37] text-[14px] font-semibold text-white transition hover:bg-[#1c302b] disabled:cursor-not-allowed disabled:bg-[#9aa49f]"
              >
                {isSubmitting ? <Loader2 size={17} className="animate-spin" /> : null}
                <span>{isSignUp ? "创建账号" : "进入工作台"}</span>
                {!isSubmitting ? <ArrowRight size={17} /> : null}
              </button>
            </form>

            <button
              type="button"
              onClick={toggleMode}
              className="mt-5 text-[13px] font-medium text-[#2f5b50] hover:text-[#20302d]"
            >
              {isSignUp ? "已有账号，去登录" : "没有账号，去注册"}
            </button>
          </div>
        </section>
      </div>
    </main>
  );
}
