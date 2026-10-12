/** A product as the shop's catalog API (products.json) returns it. Prices are in minor units (cents). */
export interface Product {
  sku: string;
  name: string;
  price: number;
  featured: number;
}
