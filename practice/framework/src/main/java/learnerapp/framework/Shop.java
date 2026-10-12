package learnerapp.framework;

/** Where the shop under test is: the base URL that every page path is resolved against. */
public record Shop(String baseUrl) {

  public Shop {
    if (!baseUrl.endsWith("/")) baseUrl = baseUrl + "/";
  }

  /** The URL of a page, for example {@code page("cart.html")}. */
  public String page(String path) {
    return baseUrl + path;
  }
}
