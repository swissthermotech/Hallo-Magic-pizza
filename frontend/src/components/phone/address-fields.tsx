import React from "react";
import { View } from "react-native";
import { makeStyles } from "@/src/theme";
import { useI18n } from "@/src/i18n";
import { Field } from "@/src/components/ui";
import type { SavedAddress } from "@/src/types";

export type OrderAddress = { street: string; number: string; npa: string; city: string; instructions: string };
export const emptyAddress = (): OrderAddress => ({ street: "", number: "", npa: "", city: "", instructions: "" });
export const fromSaved = (a: SavedAddress): OrderAddress => ({ street: a.street, number: a.number, npa: a.npa, city: a.city, instructions: a.instructions || "" });

/** Street / number / NPA / city / instructions inputs shared by the phone-order flow and the staff customer editor. */
export function AddressFields({ a, onChange, prefix }: { a: OrderAddress; onChange: (a: OrderAddress) => void; prefix: string }) {
  const styles = useStyles();
  const { t } = useI18n();
  const set = (k: keyof OrderAddress) => (v: string) => onChange({ ...a, [k]: v });
  return (
    <View style={{ gap: 10 }}>
      <View style={styles.two}>
        <Field label={`${t("street")} *`} value={a.street} onChangeText={set("street")} style={{ flex: 3 }} testID={`${prefix}-street`} />
        <Field label={t("number")} value={a.number} onChangeText={set("number")} style={{ flex: 1 }} testID={`${prefix}-number`} />
      </View>
      <View style={styles.two}>
        <Field label={`${t("npa")} *`} value={a.npa} onChangeText={set("npa")} keyboardType="number-pad" style={{ flex: 1 }} testID={`${prefix}-npa`} />
        <Field label={`${t("city")} *`} value={a.city} onChangeText={set("city")} style={{ flex: 2 }} testID={`${prefix}-city`} />
      </View>
      <Field label={t("deliveryInstructions")} value={a.instructions} onChangeText={set("instructions")} testID={`${prefix}-instructions`} />
    </View>
  );
}

const useStyles = makeStyles(() => ({
  two: { flexDirection: "row", gap: 10 },
}));
