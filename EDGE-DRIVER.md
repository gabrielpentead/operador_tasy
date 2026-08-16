Edge specific functionality

These are capabilities and features specific to Microsoft Edge browsers.

Microsoft Edge is implemented with Chromium, with the earliest supported version of v79. Similar to Chrome, the major version number of edgedriver must match the major version of the Edge browser.



Options

Capabilities common to all browsers are described on the Options page.



Capabilities unique to Chromium are documented at Google’s page for Capabilities \& ChromeOptions



Starting an Edge session with basic defined options looks like this:



Java

Python

CSharp

Ruby

JavaScript

Kotlin

    options = get\_default\_edge\_options()

    driver = webdriver.Edge(options=options)

View Complete Code

View on GitHub

Arguments

The args parameter is for a list of command line switches to be used when starting the browser. There are two excellent resources for investigating these arguments:



Chrome Flags for Tooling

List of Chromium Command Line Switches

Commonly used args include --start-maximized, --headless=new and --user-data-dir=...



Add an argument to options:



Java

Python

CSharp

Ruby

JavaScript

Kotlin

    options.add\_argument("--start-maximized")

View Complete Code

View on GitHub

Start browser in a specified location

The binary parameter takes the path of an alternate location of browser to use. With this parameter you can use chromedriver to drive various Chromium based browsers.



Add a browser location to options:



Java

Python

CSharp

Ruby

JavaScript

Kotlin

    options.binary\_location = edge\_bin

View Complete Code

View on GitHub

Add extensions

The extensions parameter accepts crx files. As for unpacked directories, please use the load-extension argument instead, as mentioned in this post.



Add an extension to options:



Java

Python

CSharp

Ruby

JavaScript

Kotlin

    options.add\_extension(extension\_file\_path)

View Complete Code

View on GitHub

Keeping browser open

Setting the detach parameter to true will keep the browser open after the process has ended, so long as the quit command is not sent to the driver.



Java

Python

CSharp

Ruby

JavaScript

Kotlin

    options.add\_experimental\_option("detach", True)

View Complete Code

View on GitHub

Excluding arguments

MSEdgedriver has several default arguments it uses to start the browser. If you do not want those arguments added, pass them into excludeSwitches. A common example is to turn the popup blocker back on. A full list of default arguments can be parsed from the Chromium Source Code



Set excluded arguments on options:



Java

Python

CSharp

Ruby

JavaScript

Kotlin

    options.add\_experimental\_option('excludeSwitches', \['disable-popup-blocking'])

View Complete Code

View on GitHub

Service

Examples for creating a default Service object, and for setting driver location and port can be found on the Driver Service page.



Log output

Getting driver logs can be helpful for debugging issues. The Service class lets you direct where the logs will go. Logging output is ignored unless the user directs it somewhere.



File output

To change the logging output to save to a specific file:



Java

Python

CSharp

Ruby

JavaScript

Kotlin

    service = webdriver.EdgeService(log\_output=log\_path)

View Complete Code

View on GitHub

Console output

To change the logging output to display in the console as STDOUT:



Java

Python

CSharp

Ruby

JavaScript

Kotlin

Selenium v4.11



    service = webdriver.EdgeService(log\_output=subprocess.STDOUT)

View Complete Code

View on GitHub

Log level

There are 6 available log levels: ALL, DEBUG, INFO, WARNING, SEVERE, and OFF. Note that --verbose is equivalent to --log-level=ALL and --silent is equivalent to --log-level=OFF, so this example is just setting the log level generically:



Java

Python

CSharp

Ruby

JavaScript

Kotlin

    service = webdriver.EdgeService(service\_args=\['--log-level=DEBUG'], log\_output=log\_path)

View Complete Code

View on GitHub

Log file features

There are 2 features that are only available when logging to a file:



append log

readable timestamps

To use them, you need to also explicitly specify the log path and log level. The log output will be managed by the driver, not the process, so minor differences may be seen.



Java

Python

CSharp

Ruby

JavaScript

Kotlin

    service = webdriver.EdgeService(service\_args=\['--append-log', '--readable-timestamp'], log\_output=log\_path)

View Complete Code

View on GitHub

Disabling build check

Edge browser and msedgedriver versions should match, and if they don’t the driver will error. If you disable the build check, you can force the driver to be used with any version of Edge. Note that this is an unsupported feature, and bugs will not be investigated.



Java

Python

CSharp

Ruby

JavaScript

Kotlin

    service = webdriver.EdgeService(service\_args=\['--disable-build-check'], log\_output=log\_path)

View Complete Code

View on GitHub

Internet Explorer Mode

Microsoft Edge can be driven in “Internet Explorer Compatibility Mode”, which uses the Internet Explorer Driver classes in conjunction with Microsoft Edge. Read the Internet Explorer page for more details.



Special Features

Some browsers have implemented additional features that are unique to them.



Casting

You can drive Chrome Cast devices with Edge, including sharing tabs



Java

Python

CSharp

Ruby

JavaScript

Kotlin

        sinks = driver.get\_sinks()

        if sinks:

            sink\_name = sinks\[0]\['name']

            driver.start\_tab\_mirroring(sink\_name)

            driver.stop\_casting(sink\_name)

View Complete Code

View on GitHub

Network conditions

You can simulate various network conditions.



Java

Python

CSharp

Ruby

JavaScript

Kotlin

    network\_conditions = {

        "offline": False,

        "latency": 20,  # 20 ms of latency

        "download\_throughput": 2000 \* 1024 / 8,  # 2000 kbps

        "upload\_throughput": 2000 \* 1024 / 8,    # 2000 kbps

    }

    driver.set\_network\_conditions(\*\*network\_conditions)

View Complete Code

View on GitHub

Logs

Java

Python

CSharp

Ruby

JavaScript

Kotlin

    logs = driver.get\_log("browser")

View Complete Code

View on GitHub

Permissions

Java

Python

CSharp

Ruby

JavaScript

Kotlin

    driver.set\_permissions('camera', 'denied')

View Complete Code

View on GitHub

DevTools

See the Chrome DevTools section for more information about using DevTools in Edge





import os

import re

import subprocess

import pytest

from selenium import webdriver

from selenium.webdriver.common.by import By



def test\_basic\_options():

    options = get\_default\_edge\_options()

    driver = webdriver.Edge(options=options)



    driver.quit()





def test\_args():

    options = get\_default\_edge\_options()



    options.add\_argument("--start-maximized")



    driver = webdriver.Edge(options=options)

    driver.get('http://selenium.dev')



    driver.quit()





def test\_set\_browser\_location(edge\_bin):

    options = get\_default\_edge\_options()



    options.binary\_location = edge\_bin



    driver = webdriver.Edge(options=options)



    driver.quit()





def test\_add\_extension():

    options = get\_default\_edge\_options()

    extension\_file\_path = os.path.abspath("tests/extensions/webextensions-selenium-example.crx")



    options.add\_extension(extension\_file\_path)



    driver = webdriver.Edge(options=options)

    driver.get("https://www.selenium.dev/selenium/web/blank.html")



    driver.quit()





def test\_keep\_browser\_open():

    options = get\_default\_edge\_options()



    options.add\_experimental\_option("detach", True)



    driver = webdriver.Edge(options=options)

    driver.get('http://selenium.dev')



    driver.quit()





def test\_exclude\_switches():

    options = get\_default\_edge\_options()



    options.add\_experimental\_option('excludeSwitches', \['disable-popup-blocking'])



    driver = webdriver.Edge(options=options)

    driver.get('http://selenium.dev')



    driver.quit()





def test\_log\_to\_file(log\_path):

    service = webdriver.EdgeService(log\_output=log\_path)



    driver = webdriver.Edge(service=service)



    with open(log\_path, 'r') as fp:

        assert "Starting Microsoft Edge WebDriver" in fp.readline()



    driver.quit()





def test\_log\_to\_stdout(capfd):

    service = webdriver.EdgeService(log\_output=subprocess.STDOUT)



    driver = webdriver.Edge(service=service)



    out, err = capfd.readouterr()

    assert "Starting Microsoft Edge WebDriver" in out



    driver.quit()





def test\_log\_level(log\_path):

    service = webdriver.EdgeService(service\_args=\['--log-level=DEBUG'], log\_output=log\_path)



    driver = webdriver.Edge(service=service)



    with open(log\_path, 'r') as f:

        assert '\[DEBUG]' in f.read()



    driver.quit()





def test\_log\_features(log\_path):

    service = webdriver.EdgeService(service\_args=\['--append-log', '--readable-timestamp'], log\_output=log\_path)



    driver = webdriver.Edge(service=service)



    with open(log\_path, 'r') as f:

        assert re.match(r"\\\[\\d\\d-\\d\\d-\\d\\d\\d\\d", f.read())



    driver.quit()





def test\_build\_checks(log\_path):

    service = webdriver.EdgeService(service\_args=\['--disable-build-check'], log\_output=log\_path)



    driver = webdriver.Edge(service=service)



    expected = "\[WARNING]: You are using an unsupported command-line switch: --disable-build-check"

    with open(log\_path, 'r') as f:

        assert expected in f.read()



    driver.quit()





def test\_set\_network\_conditions():

    driver = webdriver.Edge()



    network\_conditions = {

        "offline": False,

        "latency": 20,  # 20 ms of latency

        "download\_throughput": 2000 \* 1024 / 8,  # 2000 kbps

        "upload\_throughput": 2000 \* 1024 / 8,    # 2000 kbps

    }

    driver.set\_network\_conditions(\*\*network\_conditions)



    driver.get("https://www.selenium.dev")



    # check whether the network conditions are set

    assert driver.get\_network\_conditions() == network\_conditions



    driver.quit()





def test\_set\_permissions():

    driver = webdriver.Edge()

    driver.get('https://www.selenium.dev')



    driver.set\_permissions('camera', 'denied')



    assert get\_permission\_state(driver, 'camera') == 'denied'

    driver.quit()





def get\_permission\_state(driver, name):

    """Helper function to query the permission state."""

    script = """

    const callback = arguments\[arguments.length - 1];

    navigator.permissions.query({name: arguments\[0]}).then(permissionStatus => {

        callback(permissionStatus.state);

    });

    """

    return driver.execute\_async\_script(script, name)





def test\_cast\_features():

    driver = webdriver.Edge()



    try:

        sinks = driver.get\_sinks()

        if sinks:

            sink\_name = sinks\[0]\['name']

            driver.start\_tab\_mirroring(sink\_name)

            driver.stop\_casting(sink\_name)

        else:

            pytest.skip("No available Cast sinks to test with.")

    finally:

        driver.quit()





def test\_get\_browser\_logs():

    driver = webdriver.Edge()

    driver.get("https://www.selenium.dev/selenium/web/bidi/logEntryAdded.html")

    driver.find\_element(By.ID, "consoleError").click()



    logs = driver.get\_log("browser")



    # Assert that at least one log contains the expected message

    assert any("I am console error" in log\['message'] for log in logs), "No matching log message found."

    driver.quit()



def get\_default\_edge\_options():

    options = webdriver.EdgeOptions()

    options.add\_argument("--no-sandbox")

    return options



















WebDriver (EdgeHTML)

18/11/2020

The W3C WebDriver API is a platform and language-neutral interface and wire protocol allowing programs or scripts to control the behavior of a web browser.



WebDriver enables developers to create automated tests that simulate user interaction. This is different from JavaScript unit tests because WebDriver has access to functionality and information that JavaScript running in the browser doesn't, and it can more accurately simulate user events or OS-level events. WebDriver can also manage testing across multiple windows, tabs and webpages in a single test session.



Here's how to get started with WebDriver for Microsoft Edge (EdgeHTML).



The Microsoft Edge (EdgeHTML) implementation of WebDriver supports both the W3C WebDriver specification and the JSON Wire Protocol for backwards compatibility with existing tests.



Getting started with WebDriver for Microsoft Edge (EdgeHTML)

Install Windows 10.

Download the appropriate Microsoft WebDriver server for your build of Windows and Microsoft Edge (EdgeHTML).

Download the WebDriver language binding of your choice. All Selenium language bindings support Microsoft Edge (EdgeHTML).

 Observação



You can find help, report issues, and file feature requests at Microsoft Edge (EdgeHTML) Feedback \& Support.



Using WebDriver

To get started using WebDriver with Microsoft Edge (EdgeHTML), check out these samples:



C# code sample for opening a browser window, navigating to bing.com and searching for 'webdriver' (GitHub Gist).

WebDriver server command line flags

List of command line flags for the WebDriver server.



Name	Description	Available Release

host	Host IP to use for the WebDriver server (default: localhost)	14393

port	Port to use for the WebDriver server (default: 17556)	14393

package	ApplicationUserModelId (AUMID) for the application to be launched by the WebDriver server	14393

verbose	Outputs requests received and responses sent by the WebDriver server	14393

silent	Outputs nothing	15063

version	Outputs the version of MicrosoftWebDriver.exe	17763

w3c	Use W3C WebDriver protocol (default option)	17763

jwp	Use JSON Wire protocol	17763

cleanup	Cleanup temporary data and registry keys set by the WebDriver server for --package. Other parameters are ignored	17763

W3C WebDriver

The support on a per command basis for the W3C WebDriver Specification.



Capabilities

Capability	Key	Status	Available Release

Browser Name	"browserName"	Supported	17763

Browser Version	"browserVersion"	Supported	17763

Platform Name	"platformName"	Supported	17763

Accept Insecure TLS Certificates	"acceptInsecureCerts"	Not Supported	N/A

Page Load Strategy	"pageLoadStrategy"	Supported	17763

Proxy Configuration	"proxy"	Not Supported	N/A

Window Dimensioning/Positioning	"setWindowRect"	Supported	17763

Session Timeouts Configuration	"timeouts"	Supported	17763

Unhandled Prompt Behavior	"unhandledPromptBehavior"	Partially Supported	17763

InPrivate	"ms:inPrivate"	Supported	17763

Extension Paths	"ms:extensionPaths"	Supported	17763

Start Page	"ms:startPage"	Supported	17763

Locator Strategies

Locator Strategy	Status	Available Release

CSS Selectors	Supported	17763

Link Text	Supported	17763

Partial Link Text	Supported	17763

Tag Name	Supported	17763

XPath	Supported	17763

Commands

HTTP Method	URI Template	Command	Status	Available Release

POST	/session	New Session	Supported	17763

DELETE	/session/{session id}	Delete Session	Supported	17763

GET	/status	Status	Supported	17763

GET	/session/{session id}/timeouts	Get Timeouts	Supported	17763

POST	/session/{session id}/timeouts	Set Timeouts	Supported	17763

POST	/session/{session id}/url	Navigate To	Supported	17763

GET	/session/{session id}/url	Get Current URL	Supported	17763

POST	/session/{session id}/back	Back	Supported	17763

POST	/session/{session id}/forward	Forward	Supported	17763

POST	/session/{session id}/refresh	Refresh	Supported	17763

GET	/session/{session id}/title	Get Title	Supported	17763

GET	/session/{session id}/window	Get Window Handle	Supported	17763

DELETE	/session/{session id}/window	Close Window	Supported	17763

POST	/session/{session id}/window	Switch to Window	Supported	17763

GET	/session/{session id}/window/handles	Get Window Handles	Supported	17763

POST	/session/{session id}/frame	Switch To Frame	Supported	17763

POST	/session/{session id}/frame/parent	Switch to Parent Frame	Supported	17763

GET	/session/{session id}/window/rect	Get Window Rect	Supported	17763

POST	/session/{session id}/window/rect	Set Window Rect	Supported	17763

POST	/session/{session id}/window/maximize	Maximize Window	Supported	17763

POST	/session/{session id}/window/minimize	Minimize Window	Supported	17763

POST	/session/{session id}/window/fullscreen	Fullscreen Window	Not Supported	N/A

GET	/session/{session id}/element/active	Get Active Element	Supported	17763

POST	/session/{session id}/element	Find Element	Supported	17763

POST	/session/{session id}/elements	Find Elements	Supported	17763

POST	/session/{session id}/element/{element id}/element	Find Element From Element	Supported	17763

POST	/session/{session id}/element/{element id}/elements	Find Elements From Element	Supported	17763

GET	/session/{session id}/element/{element id}/selected	Is Element Selected	Supported	17763

GET	/session/{session id}/element/{element id}/attribute/{name}	Get Element Attribute	Supported	17763

GET	/session/{session id}/element/{element id}/property/{name}	Get Element Property	Supported	17763

GET	/session/{session id}/element/{element id}/css/{property name}	Get Element CSS Value	Supported	17763

GET	/session/{session id}/element/{element id}/text	Get Element Text	Supported	17763

GET	/session/{session id}/element/{element id}/name	Get Element Tag Name	Supported	17763

GET	/session/{session id}/element/{element id}/rect	Get Element Rect	Supported	17763

GET	/session/{session id}/element/{element id}/enabled	Is Element Enabled	Supported	17763

POST	/session/{session id}/element/{element id}/click	Element Click	Supported	17763

POST	/session/{session id}/element/{element id}/clear	Element Clear	Supported	17763

POST	/session/{session id}/element/{element id}/sendKeys	Element Send Keys	Supported	17763

GET	/session/{session id}/source	Get Page Source	Supported	17763

POST	/session/{session id}/execute/sync	Execute Script	Supported	17763

POST	/session/{session id}/execute/async	Execute Async Script	Supported	17763

GET	/session/{session id}/cookie	Get All Cookies	Supported	17763

GET	/session/{session id}/cookie/{name}	Get Named Cookie	Supported	17763

POST	/session/{session id}/cookie	Add Cookie	Supported	17763

DELETE	/session/{session id}/cookie/{name}	Delete Cookie	Supported	17763

DELETE	/session/{session id}/cookie	Delete All Cookies	Supported	17763

POST	/session/{session id}/actions	Perform Actions	Supported	17763

DELETE	/session/{session id}/actions	Release Actions	Supported	17763

POST	/session/{session id}/alert/dismiss	Dismiss Alert	Supported	17763

POST	/session/{session id}/alert/accept	Accept Alert	Supported	17763

GET	/session/{session id}/alert/text	Get Alert Text	Supported	17763

POST	/session/{session id}/alert/text	Send Alert Text	Supported	17763

GET	/session/{session id}/screenshot	Take Screenshot	Supported	17763

GET	/session/{session id}/screenshot/{element id}	Take Element Screenshot	Supported	17763

JSON Wire Protocol

The support on a per command basis for the JSON Wire Protocol.



Commands

HTTP Method	Path	Status	Available Release

GET	/status	Supported	10240

POST	/session	Supported	10240

GET	/sessions	Supported	10240

GET	/session/:sessionId	Supported	10240

DELETE	/session/:sessionId	Supported	10240

POST	/session/:sessionId/timeouts	Supported	10240

POST	/session/:sessionId/timeouts/async\_script	Not Supported	N/A

POST	/session/:sessionId/timeouts/implicit\_wait	Supported	10586

GET	/session/:sessionId/window\_handle	Supported	10586

GET	/session/:sessionId/window\_handles	Supported	10586

GET	/session/:sessionId/url	Supported	10240

POST	/session/:sessionId/url	Supported	10240

POST	/session/:sessionId/forward	Supported	10240

POST	/session/:sessionId/back	Supported	10240

POST	/session/:sessionId/refresh	Supported	10240

POST	/session/:sessionId/execute	Supported	10240

POST	/session/:sessionId/execute\_async	Supported	10586

GET	/session/:sessionId/screenshot	Supported	10240

GET	/session/:sessionId/ime/available\_engines	Not Supported	N/A

GET	/session/:sessionId/ime/active\_engine	Not Supported	N/A

GET	/session/:sessionId/ime/activated	Not Supported	N/A

POST	/session/:sessionId/ime/deactivate	Not Supported	N/A

POST	/session/:sessionId/ime/activate	Not Supported	N/A

POST	/session/:sessionId/frame	Supported	10586

POST	/session/:sessionId/frame/parent	Supported	10586

POST	/session/:sessionId/window	Supported	10586

DELETE	/session/:sessionId/window	Supported	10586

POST	/session/:sessionId/window/:windowHandle/size	Supported	10586

GET	/session/:sessionId/window/:windowHandle/size	Supported	10586

POST	/session/:sessionId/window/:windowHandle/position	Supported	10586

GET	/session/:sessionId/window/:windowHandle/position	Supported	10586

GET	/session/:sessionId/window/:windowHandle/maximize	Supported	10586

GET	/session/:sessionId/cookie	Supported	10586

POST	/session/:sessionId/cookie	Supported	10240

DELETE	/session/:sessionId/cookie	Supported	10586

DELETE	/session/:sessionId/cookie/:name	Supported	10240

GET	/session/:sessionId/source	Supported	10586

GET	/session/:sessionId}/title	Supported	10240

POST	/session/:sessionId/element	Supported	10586

POST	/session/:sessionId/elements	Supported	10586

POST	/session/:sessionId/element/active	Supported	10586

GET	/session/:sessionId/element/:id	Not Supported	N/A

POST	/session/:sessionId/element/:id/element	Supported	10586

POST	/session/:sessionId/element/:id/elements	Supported	10586

POST	/session/:sessionId/element/:id/click	Supported	10240

POST	/session/:sessionId/element/:id/submit	Supported	10586

GET	/session/:sessionId/element/:id/text	Supported	10240

POST	/session/:sessionId/element/:id/value	Supported	10240

POST	/session/:sessionId/keys	Supported	10586

GET	/session/:sessionId/element/:id/name	Supported	10240

POST	/session/:sessionId/element/:id/clear	Supported	10240

GET	/session/:sessionId/element/:id/selected	Supported	10240

GET	/session/:sessionId/element/:id/enabled	Supported	10240

GET	/session/:sessionId/element/:id/attribute/:name	Supported	10240

GET	/session/:sessionId/element/:id/equals/:other	Supported	10586

GET	/session/:sessionId/element/:id/displayed	Supported	10240

GET	/session/:sessionId/element/:id/location	Supported	10586

GET	/session/:sessionId/element/:id/location\_in\_view	Supported	10586

GET	/session/:sessionId/element/:id/size	Supported	10586

GET	/session/:sessionId/element/:id/css/:propertyName	Supported	10240

GET	/session/:sessionId/orientation	Not Supported	N/A

POST	/session/:sessionId/orientation	Not Supported	N/A

GET	/session/:sessionId/alert\_text	Supported	10240

POST	/session/:sessionId/alert\_text	Supported	10586

POST	/session/:sessionId/accept\_alert	Supported	10240

POST	/session/:sessionId/dismiss\_alert	Supported	10240

POST	/session/:sessionId/moveto	Supported	10586

POST	/session/:sessionId/click	Supported	10240

POST	/session/:sessionId/buttondown	Supported	10586

POST	/session/:sessionId/buttonup	Supported	10586

POST	/session/:sessionId/doubleclick	Supported	10586

POST	/session/:sessionId/touch/click	Not Supported	N/A

POST	/session/:sessionId/touch/down	Not Supported	N/A

POST	/session/:sessionId/touch/up	Not Supported	N/A

POST	/session/:sessionId/touch/move	Not Supported	N/A

POST	/session/:sessionId/touch/scroll	Not Supported	N/A

POST	/session/:sessionId/touch/scroll	Not Supported	N/A

POST	/session/:sessionId/touch/doubleclick	Not Supported	N/A

POST	/session/:sessionId/touch/longclick	Not Supported	N/A

POST	/session/:sessionId/touch/flick	Not Supported	N/A

POST	/session/:sessionId/touch/flick	Not Supported	N/A

GET	/session/:sessionId/location	Supported	10586

POST	/session/:sessionId/location	Supported	10586

GET	/session/:sessionId/local\_storage	Supported	10586

POST	/session/:sessionId/local\_storage	Supported	10586

DELETE	/session/:sessionId/local\_storage	Supported	10586

GET	/session/:sessionId/local\_storage/key/:key	Supported	10586

DELETE	/session/:sessionId/local\_storage/key/:key	Supported	10586

GET	/session/:sessionId/local\_storage/size	Supported	10586

GET	/session/:sessionId/session\_storage	Supported	10586

POST	/session/:sessionId/session\_storage	Supported	10586

DELETE	/session/:sessionId/session\_storage	Supported	10586

GET	/session/:sessionId/session\_storage/key/:key	Supported	10586

DELETE	/session/:sessionId/session\_storage/key/:key	Supported	10586

GET	/session/:sessionId/session\_storage/size	Supported	10586

GET	/session/:sessionId/log	Not Supported	N/A

GET	/session/:sessionId/log/types	Not Supported	N/A

GET	/session/:sessionId/application\_cache/status	Supported	10586



