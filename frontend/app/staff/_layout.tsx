import React from "react";
import { ActivityIndicator, View } from "react-native";
import { Redirect, Stack, useGlobalSearchParams, usePathname } from "expo-router";
import { themes } from "@/src/theme";
import { homeFor, useStaff } from "@/src/staff-auth";
import { StaffSoundProvider } from "@/src/staff-sound";

export default function StaffLayout() {
  const { ready, unlocked, role } = useStaff();
  const pathname = usePathname();
  const isLogin = pathname.startsWith("/staff/login");
  const { switch: switching } = useGlobalSearchParams<{ switch?: string }>();

  if (!ready) {
    return (
      <View style={{ flex: 1, alignItems: "center", justifyContent: "center", backgroundColor: themes.light.surface }}>
        <ActivityIndicator color={themes.light.brandPrimary} />
      </View>
    );
  }
  if (!unlocked && !isLogin) return <Redirect href="/staff/login" />;
  // Already unlocked on this device -> go to the role's home, unless the user explicitly wants to switch account (?switch=1)
  if (unlocked && isLogin && !switching) return <Redirect href={homeFor(role!)} />;
  if (isLogin) return <Stack screenOptions={{ headerShown: false, contentStyle: { backgroundColor: themes.light.surface } }} />;
  // Role boundaries: drivers only see /driver, phone role only /phone-orders, admin & closing are manager-only
  if (unlocked && role && role.startsWith("driver")) return <Redirect href="/driver" />;
  if (unlocked && role === "phone" && !pathname.startsWith("/staff/ticket")) return <Redirect href="/phone-orders" />;
  if (unlocked && role !== "manager" && (pathname.startsWith("/staff/admin") || pathname.startsWith("/staff/closing"))) return <Redirect href="/staff" />;

  // New-order alert lives at layout level: it keeps ringing while the manager is in Cuisine / Clients / Admin…
  return (
    <StaffSoundProvider active={role === "manager" || role === "kitchen"}>
      <Stack screenOptions={{ headerShown: false, contentStyle: { backgroundColor: themes.light.surface } }} />
    </StaffSoundProvider>
  );
}
