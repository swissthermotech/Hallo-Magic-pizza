import React from "react";
import { ActivityIndicator, View } from "react-native";
import { Redirect, Stack, usePathname } from "expo-router";
import { themes } from "@/src/theme";
import { useStaff } from "@/src/staff-auth";

export default function StaffLayout() {
  const { ready, unlocked } = useStaff();
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
  if (unlocked && isLogin) return <Redirect href="/staff" />;

  return <Stack screenOptions={{ headerShown: false, contentStyle: { backgroundColor: themes.light.surface } }} />;
}
