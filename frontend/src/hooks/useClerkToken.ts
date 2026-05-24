"use client";
import { useAuth } from "@clerk/nextjs";

export function useClerkToken() {
  const { getToken } = useAuth();
  return { getToken: () => getToken() };
}
