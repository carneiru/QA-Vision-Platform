"""parse_file dispatches on the XML root element: JUnit, TRX (vstest),
NUnit 3, xUnit.net v2 and TestNG all land in the same result shape."""
from datetime import datetime, timezone

from qav_collector.formats import parse_file


def write(tmp_path, text, name="report.xml"):
    path = tmp_path / name
    path.write_text(text, encoding="utf-8")
    return str(path)


def by_name(parsed):
    return {r["name"]: r for r in parsed.results}


def test_junit_still_parses_through_the_dispatcher(tmp_path):
    path = write(tmp_path, (
        '<testsuites><testsuite name="s" timestamp="2026-10-01T10:00:00Z" time="1.7">'
        '<testcase classname="c" name="ok" time="0.1"/>'
        '</testsuite></testsuites>'
    ))
    parsed = parse_file(path)
    assert not parsed.skipped
    assert by_name(parsed)["ok"]["status"] == "passed"
    assert parsed.suite_timestamps == [datetime(2026, 10, 1, 10, tzinfo=timezone.utc)]


TRX = """<TestRun xmlns="http://microsoft.com/schemas/VisualStudio/TeamTest/2010">
  <Times start="2026-10-01T10:00:00+00:00" finish="2026-10-01T10:00:02+00:00"/>
  <Results>
    <UnitTestResult testId="id1" testName="Adds" outcome="Passed" duration="00:00:01.5000000"/>
    <UnitTestResult testId="id2" testName="Pays" outcome="Failed" duration="00:00:00.2000000">
      <Output><ErrorInfo><Message>boom</Message><StackTrace>at Cart.Pays()</StackTrace></ErrorInfo></Output>
    </UnitTestResult>
    <UnitTestResult testId="id3" testName="Times" outcome="Timeout"/>
    <UnitTestResult testId="id4" testName="Aborts" outcome="Aborted"/>
    <UnitTestResult testId="id5" testName="Later" outcome="NotExecuted"/>
  </Results>
  <TestDefinitions>
    <UnitTest id="id1"><TestMethod className="Shop.Tests.Cart" name="Adds"/></UnitTest>
    <UnitTest id="id2"><TestMethod className="Shop.Tests.Cart" name="Pays"/></UnitTest>
  </TestDefinitions>
</TestRun>"""


def test_trx(tmp_path):
    parsed = parse_file(write(tmp_path, TRX))
    assert not parsed.skipped
    results = by_name(parsed)
    assert results["Adds"]["status"] == "passed"
    assert results["Adds"]["duration_ms"] == 1500
    assert results["Adds"]["class_name"] == "Shop.Tests.Cart"
    assert results["Pays"]["status"] == "failed"
    assert results["Pays"]["message"] == "boom"
    assert "at Cart.Pays()" in results["Pays"]["details"]
    assert results["Times"]["status"] == "failed"
    assert results["Aborts"]["status"] == "errored"
    assert results["Later"]["status"] == "skipped"
    assert results["Later"]["class_name"] == ""  # no definition for id5
    assert parsed.suite_timestamps == [datetime(2026, 10, 1, 10, tzinfo=timezone.utc)]
    assert parsed.suite_seconds == 2.0


NUNIT = """<test-run start-time="2026-10-01T10:00:00Z" duration="1.7">
  <test-suite type="Assembly" name="Shop.Tests.dll">
    <test-suite type="TestFixture" name="Cart">
      <test-case name="Adds" classname="Shop.Tests.Cart" result="Passed" duration="1.5"/>
      <test-case name="Pays" classname="Shop.Tests.Cart" result="Failed" duration="0.2">
        <failure><message>boom</message><stack-trace>at Cart.Pays()</stack-trace></failure>
      </test-case>
      <test-case name="Errors" classname="Shop.Tests.Cart" result="Failed" label="Error">
        <failure><message>NullReferenceException</message></failure>
      </test-case>
      <test-case name="Later" classname="Shop.Tests.Cart" result="Skipped"/>
    </test-suite>
  </test-suite>
</test-run>"""


def test_nunit3(tmp_path):
    parsed = parse_file(write(tmp_path, NUNIT))
    assert not parsed.skipped
    results = by_name(parsed)
    assert results["Adds"]["status"] == "passed"
    assert results["Adds"]["duration_ms"] == 1500
    assert results["Adds"]["suite"] == "Shop.Tests.dll"
    assert results["Adds"]["class_name"] == "Shop.Tests.Cart"
    assert results["Pays"]["status"] == "failed"
    assert results["Pays"]["message"] == "boom"
    assert results["Errors"]["status"] == "errored"
    assert results["Later"]["status"] == "skipped"
    assert parsed.suite_timestamps == [datetime(2026, 10, 1, 10, tzinfo=timezone.utc)]
    assert parsed.suite_seconds == 1.7


XUNIT = """<assemblies>
  <assembly name="C:\\build\\Shop.Tests.dll" run-date="2026-10-01" run-time="10:00:00" time="1.7">
    <collection name="Test collection for Shop.Tests.Cart">
      <test name="Shop.Tests.Cart.Adds" type="Shop.Tests.Cart" method="Adds" result="Pass" time="1.5"/>
      <test name="Shop.Tests.Cart.Pays" type="Shop.Tests.Cart" method="Pays" result="Fail" time="0.2">
        <failure exception-type="AssertException"><message>boom</message><stack-trace>at Cart.Pays()</stack-trace></failure>
      </test>
      <test name="Shop.Tests.Cart.Later" type="Shop.Tests.Cart" method="Later" result="Skip">
        <reason><![CDATA[flaky on CI]]></reason>
      </test>
    </collection>
  </assembly>
</assemblies>"""


def test_xunit2(tmp_path):
    parsed = parse_file(write(tmp_path, XUNIT))
    assert not parsed.skipped
    results = by_name(parsed)
    assert results["Adds"]["status"] == "passed"
    assert results["Adds"]["duration_ms"] == 1500
    assert results["Adds"]["suite"] == "Shop.Tests.dll"
    assert results["Adds"]["class_name"] == "Shop.Tests.Cart"
    assert results["Pays"]["status"] == "failed"
    assert results["Pays"]["message"] == "boom"
    assert results["Later"]["status"] == "skipped"
    assert results["Later"]["message"] == "flaky on CI"
    assert parsed.suite_timestamps == [datetime(2026, 10, 1, 10, tzinfo=timezone.utc)]
    assert parsed.suite_seconds == 1.7


TESTNG = """<testng-results>
  <suite name="regression" started-at="2026-10-01T10:00:00Z" duration-ms="1700">
    <test name="checkout">
      <class name="com.shop.CartTest">
        <test-method name="setUp" status="PASS" is-config="true" duration-ms="10"/>
        <test-method name="adds" status="PASS" duration-ms="1500"/>
        <test-method name="pays" status="FAIL" duration-ms="200">
          <exception class="java.lang.AssertionError"><message>boom</message>
            <full-stacktrace>at CartTest.pays()</full-stacktrace></exception>
        </test-method>
        <test-method name="later" status="SKIP" duration-ms="0"/>
      </class>
    </test>
  </suite>
</testng-results>"""


def test_testng(tmp_path):
    parsed = parse_file(write(tmp_path, TESTNG))
    assert not parsed.skipped
    results = by_name(parsed)
    assert "setUp" not in results  # configuration methods are not tests
    assert results["adds"]["status"] == "passed"
    assert results["adds"]["duration_ms"] == 1500
    assert results["adds"]["suite"] == "regression"
    assert results["adds"]["class_name"] == "com.shop.CartTest"
    assert results["pays"]["status"] == "failed"
    assert results["pays"]["message"] == "boom"
    assert "at CartTest.pays()" in results["pays"]["details"]
    assert results["later"]["status"] == "skipped"
    assert parsed.suite_timestamps == [datetime(2026, 10, 1, 10, tzinfo=timezone.utc)]
    assert parsed.suite_seconds == 1.7


def test_an_unknown_root_is_skipped_with_the_supported_list(tmp_path):
    parsed = parse_file(write(tmp_path, "<report><case/></report>"))
    assert parsed.skipped
    assert "root element is <report>" in parsed.warnings[0]
