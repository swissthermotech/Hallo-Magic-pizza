import React from "react";
import { ActivityIndicator, View } from "react-native";
import { Redirect, Stack, usePathname } from "expo-router";
import { themes } from "@/src/theme";
import { homeFor, useStaff } from "@/src/staff-auth";

export default function StaffLayout() {
  const { ready, unlocked, role } = useStaff();
  const pathname = usePathname();
  const isLogin = pathname.startsWith("/staff/login");

  if (!ready) {
    return (
      <View style={{ flex: 1, alignItems: "center", justifyContent: "center", backgroundColor: themes.light.surface }}>
        <ActivityIndicator color={themes.light.brandPrimary} />
      </View>
    );
  }
  if (!unlocked && !isLogin) return <Redirect href="/staff/login" />;
  if (unlocked && isLogin) return <Redirect href={homeFor(role!)} />;
  // Role boundaries: drivers only see /driver, phone role only /phone-orders, admin & closing are manager-only
  if (unlocked && role && role.startsWith("driver")) return <Redirect href="/driver" />;
  if (unlocked && role === "phone") return <Redirect href="/phone-orders" />;
  if (unlocked && role !== "manager" && (pathname.startsWith("/staff/admin") || pathname.startsWith("/staff/closing"))) return <Redirect href="/staff" />;

  return <Stack screenOptions={{ headerShown: false, contentStyle: { backgroundColor: themes.light.surface } }} />;
}
