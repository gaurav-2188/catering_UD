/**
 * Computes tax-inclusive billing splits across total values on the client side.
 * Formula:
 * Pre-Tax Subtotal = total_amount / (1 + (gst_percent / 100))
 * Total Tax Amount = total_amount - Pre-Tax Subtotal
 * CGST = Total Tax Amount / 2
 * SGST = Total Tax Amount / 2
 */
export function calculateTaxSplits(totalAmount, gstPercent = 18) {
  const total = parseFloat(totalAmount || 0);
  const gstRate = parseFloat(gstPercent || 0);

  const preTaxSubtotal = total / (1 + (gstRate / 100));
  const totalTaxAmount = total - preTaxSubtotal;
  const cgstAmount = totalTaxAmount / 2;
  const sgstAmount = totalTaxAmount / 2;

  return {
    totalAmount: total,
    gstPercent: gstRate,
    preTaxSubtotal: parseFloat(preTaxSubtotal.toFixed(2)),
    totalTaxAmount: parseFloat(totalTaxAmount.toFixed(2)),
    cgstAmount: parseFloat(cgstAmount.toFixed(2)),
    sgstAmount: parseFloat(sgstAmount.toFixed(2))
  };
}
