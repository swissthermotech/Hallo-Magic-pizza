import React from "react";
import { Text, View } from "react-native";
import { makeStyles } from "@/src/theme";
import { FONT_TEXT } from "./ui";
import type { OrderItem } from "@/src/types";

/** Driver / livreur order lines – one clearly separated block per pizza:
 *  line 1: quantity + size + name      → "2x 32 CM HAWAIANA"
 *  line 2: modifications, indented     → "Sans champignons · + câpres · Pâte sans gluten · Note : …" */
export function DriverItems({ items, orderId }: { items: OrderItem[]; orderId: string }) {
  const styles = useStyles();
  const sizeLabel = (label: string) => label.replace(/\s*cm$/i, " CM").toUpperCase();
  return (
    <View style={styles.list} testID={`driver-items-${orderId}`}>
      {items.map((it, idx) => {
        const mods = [
          ...it.removed_ingredients.map((r) => `Sans ${r.fr}`),
          ...it.extras.map((e) => `+ ${e.quantity > 1 ? `${e.quantity}x ` : ""}${e.name.fr}`),
          ...(it.options || []).map((op) => op.name.fr),
          ...(it.note ? [`Note : ${it.note}`] : []),
        ];
        const halfMods = it.half
          ? [...it.half.removed_ingredients.map((r) => `Sans ${r.fr}`), ...(it.half.note ? [`Note : ${it.half.note}`] : [])]
          : [];
        const title = `${it.quantity}x ${it.size ? `${sizeLabel(it.size.label)} ` : ""}${it.half ? `MOITIÉ/MOITIÉ : ${it.name.fr.toUpperCase()} / ${it.half.name.fr.toUpperCase()}` : it.name.fr.toUpperCase()}`;
        return (
          <View key={idx} style={[styles.item, idx > 0 && styles.itemSep]} testID={`driver-item-${orderId}-${idx}`}>
            <Text style={styles.title}>{title}</Text>
            {mods.length ? <Text style={styles.mods}>{it.half ? `½ ${it.name.fr} : ` : ""}{mods.join(" · ")}</Text> : null}
            {halfMods.length ? <Text style={styles.mods}>½ {it.half!.name.fr} : {halfMods.join(" · ")}</Text> : null}
          </View>
        );
      })}
    </View>
  );
}

const useStyles = makeStyles((colors) => ({
  list: { borderRadius: 12, borderWidth: 1, borderColor: colors.border, backgroundColor: colors.surface, overflow: "hidden" },
  item: { paddingVertical: 10, paddingHorizontal: 12, gap: 3 },
  itemSep: { borderTopWidth: 1, borderTopColor: colors.border },
  title: { fontFamily: FONT_TEXT, fontSize: 17, fontWeight: "800", color: colors.onSurface, lineHeight: 22 },
  mods: { fontFamily: FONT_TEXT, fontSize: 15, fontWeight: "600", color: colors.brandPrimary, lineHeight: 21, paddingLeft: 16 },
}));
