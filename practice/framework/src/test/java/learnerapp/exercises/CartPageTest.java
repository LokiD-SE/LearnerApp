package learnerapp.exercises;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.lang.reflect.Method;
import java.lang.reflect.Modifier;
import java.util.Arrays;
import java.util.List;
import learnerapp.exercises.pages.CartPage;
import learnerapp.framework.Shop;
import learnerapp.framework.ShopExtension;
import learnerapp.framework.pages.CatalogPage;
import learnerapp.framework.pages.CheckoutPage;
import org.junit.jupiter.api.Tag;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.openqa.selenium.By;
import org.openqa.selenium.WebDriver;
import org.openqa.selenium.WebElement;

@Tag("exercise")
@ExtendWith(ShopExtension.class)
class CartPageTest {

  private static final String ESPRESSO = "Espresso beans 1 kg";
  private static final String OAT_MILK = "Oat milk 1 L";

  /** Two espresso beans (2 x 18.99) and one oat milk (2.49) in the cart. */
  private static CartPage cartWithThreeItems(WebDriver driver, Shop shop) {
    CatalogPage.open(driver, shop).addToCart("espresso-beans").addToCart("espresso-beans").addToCart("oat-milk");
    return CartPage.open(driver, shop);
  }

  @Test
  void showsWhatIsInTheCart(WebDriver driver, Shop shop) {
    CartPage cart = cartWithThreeItems(driver, shop);
    assertEquals(List.of(ESPRESSO, OAT_MILK), cart.productNames());
    assertEquals(2, cart.quantityOf(ESPRESSO));
    assertEquals(1, cart.quantityOf(OAT_MILK));
    assertEquals(0, cart.quantityOf("Hand grinder"), "not in the cart");
    assertEquals(2 * 1899 + 249, cart.totalMinor());
    assertFalse(cart.isEmpty());
  }

  @Test
  void anIncreaseIsVisibleAsSoonAsTheMethodReturns(WebDriver driver, Shop shop) {
    CartPage cart = cartWithThreeItems(driver, shop).increaseQuantity(OAT_MILK);
    assertEquals(2, cart.quantityOf(OAT_MILK), "increaseQuantity must wait for the saved quantity");
    assertEquals(2 * 1899 + 2 * 249, cart.totalMinor());
  }

  @Test
  void removingLinesEmptiesTheCart(WebDriver driver, Shop shop) {
    CartPage cart = cartWithThreeItems(driver, shop).remove(ESPRESSO);
    assertEquals(List.of(OAT_MILK), cart.productNames(), "remove must wait until the line is gone");
    assertEquals(249, cart.totalMinor());
    assertTrue(cart.remove(OAT_MILK).isEmpty());
  }

  @Test
  void leadsToTheCheckout(WebDriver driver, Shop shop) {
    CheckoutPage checkout = cartWithThreeItems(driver, shop).goToCheckout();
    assertEquals(2 * 1899 + 249, checkout.totalMinor());
  }

  @Test
  void keepsSeleniumInsideThePageObject() {
    for (Method method : CartPage.class.getMethods()) {
      if (method.getDeclaringClass() != CartPage.class) continue;
      Class<?> type = method.getReturnType();
      assertFalse(
          WebElement.class.isAssignableFrom(type) || By.class.isAssignableFrom(type),
          method.getName() + " hands out a " + type.getSimpleName() + " - return data or a page object");
    }
    assertTrue(
        Arrays.stream(CartPage.class.getFields()).noneMatch(f -> Modifier.isPublic(f.getModifiers())),
        "no public fields - locators stay private");
  }
}
