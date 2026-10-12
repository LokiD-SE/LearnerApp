package learnerapp.strings;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;

import java.util.List;
import org.junit.jupiter.api.Tag;
import org.junit.jupiter.api.Test;

@Tag("exercise")
class ReportLineTest {

  @Test
  void splitsOnThePipe() {
    assertEquals(List.of("pay_81Fz", "SUCCEEDED", "1999", "EUR"), ReportLine.fields("pay_81Fz|SUCCEEDED|1999|EUR"));
  }

  @Test
  void keepsEmptyFieldsInTheMiddleAndAtTheEnd() {
    assertEquals(List.of("pay_81Fz", "", "1999", ""), ReportLine.fields("pay_81Fz||1999|"));
    assertEquals(List.of("", "", ""), ReportLine.fields("||"));
    assertEquals(List.of(""), ReportLine.fields(""));
  }

  @Test
  void stripsAnyWhiteSpaceAroundFields() {
    assertEquals(List.of("pay_81Fz", "SUCCEEDED"), ReportLine.fields("  pay_81Fz | SUCCEEDED\t"));
    // U+2003 EM SPACE is white space, but above U+0020, so trim() keeps it
    assertEquals(List.of("pay_81Fz", "EUR"), ReportLine.fields(" pay_81Fz |EUR"));
  }

  @Test
  void rejectsNull() {
    assertThrows(IllegalArgumentException.class, () -> ReportLine.fields(null));
  }
}
