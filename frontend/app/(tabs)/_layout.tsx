import React from "react";
import { Platform, Text, View, type ColorValue } from "react-native";
import { Tabs } from "expo-router";
import { NativeTabs } from "expo-router/unstable-native-tabs";
import { Feather } from "@react-native-vector-icons/feather";
import { useTheme } from "@/src/theme";
import { useI18n } from "@/src/i18n";
import { useCart } from "@/src/cart";
import { FONT_TEXT } from "@/src/components/ui";

const isIOS26 = Platform.OS === "ios" && parseInt(String(Platform.Version), 10) >= 26;

export default function TabsLayout() {
  const { colors } = useTheme();
  const { t } = useI18n();
  const { count } = useCart();

  if (isIOS26) {
    return (
      <NativeTabs>
        <NativeTabs.Trigger name="index">
          <NativeTabs.Trigger.Icon sf="fork.knife" />
          <NativeTabs.Trigger.Label>{t("menu")}</NativeTabs.Trigger.Label>
        </NativeTabs.Trigger>
        <NativeTabs.Trigger name="cart">
          <NativeTabs.Trigger.Icon sf="bag" />
          <NativeTabs.Trigger.Label>{count > 0 ? `${t("cart")} (${count})` : t("cart")}</NativeTabs.Trigger.Label>
        </NativeTabs.Trigger>
        <NativeTabs.Trigger name="orders">
          <NativeTabs.Trigger.Icon sf="clock" />
          <NativeTabs.Trigger.Label>{t("orders")}</NativeTabs.Trigger.Label>
        </NativeTabs.Trigger>
        <NativeTabs.Trigger name="more">
          <NativeTabs.Trigger.Icon sf="ellipsis.circle" />
          <NativeTabs.Trigger.Label>{t("more")}</NativeTabs.Trigger.Label>
        </NativeTabs.Trigger>
      </NativeTabs>
    );
  }

  const icon = (name: React.ComponentProps<typeof Feather>["name"], badge?: number) => {
    const TabIcon = ({ color }: { color: ColorValue }) => (
      <View style={{ width: 28, height: 28, alignItems: "center", justifyContent: "center" }}>
        <Feather name={name} size={22} color={color as string} />
        {badge ? (
          <View style={{ position: "absolute", top: -4, right: -8, minWidth: 18, height: 18, borderRadius: 9, backgroundColor: colors.brandPrimary, alignItems: "center", justifyContent: "center", paddingHorizontal: 4 }}>
            <Text style={{ color: colors.onBrandPrimary, fontSize: 11, fontWeight: "800", fontFamily: FONT_TEXT }}>{badge}</Text>
          </View>
        ) : null}
      </View>
    );
    return TabIcon;
  };

  return (
    <Tabs
      screenOptions={{
        headerShown: false,
        tabBarActiveTintColor: colors.brandPrimary,
        tabBarInactiveTintColor: colors.muted,
        tabBarStyle: { backgroundColor: colors.surfaceSecondary, borderTopColor: colors.border, ...(Platform.OS === "web" ? { height: 64 } : {}) },
        tabBarItemStyle: { alignSelf: "center" },
        tabBarLabelStyle: { fontFamily: FONT_TEXT, fontSize: 12, fontWeight: "600" },
      }}
    >
      <Tabs.Screen name="index" options={{ title: t("menu"), tabBarIcon: icon("grid"), tabBarButtonTestID: "tab-menu" }} />
      <Tabs.Screen name="cart" options={{ title: t("cart"), tabBarIcon: icon("shopping-bag", count), tabBarButtonTestID: "tab-cart" }} />
      <Tabs.Screen name="orders" options={{ title: t("orders"), tabBarIcon: icon("clock"), tabBarButtonTestID: "tab-orders" }} />
      <Tabs.Screen name="more" options={{ title: t("more"), tabBarIcon: icon("more-horizontal"), tabBarButtonTestID: "tab-more" }} />
    </Tabs>
  );
}
