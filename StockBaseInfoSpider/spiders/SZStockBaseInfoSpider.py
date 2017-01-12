# -*- coding: utf-8 -*-


# 上交所A股列表地址，页面是异步查询加载，不能用常规的爬虫方法
# http://www.sse.com.cn/assortment/stock/list/share/
from scrapy import Spider
from bs4 import BeautifulSoup
from StockBaseInfoSpider.items import StockbaseinfospiderItem
import spynner
import pyquery
from StockBaseInfoSpider.dbservice.DbService import DbService

class SZStockBaseInfoSpider(Spider):
    name = "SZStockBaseInfoSpider"
    allowed_domains = []
    start_urls = [
        'http://www.szse.cn/main/marketdata/jypz/colist/'
    ]

    download_delay = 1

    exchange = 'SZ'

    dbService = DbService()

    # 这个地方没有直接解析response，而是用browser重新加载了当前的self.start_urls[0]，这个parse方法只是一个爬虫的入口，具体实现在里面
    def parse(self, response):
        print 'SZ深证股票列表爬虫开始爬取。。。'
        browser = spynner.Browser()
        browser.create_webview()
        browser.set_html_parser(pyquery.PyQuery)
        browser.load_jquery(True)
        browser.load(self.start_urls[0], 10)
        # 第一次设置为1，是为了加载第一页数据后不触发下一页button的click事件
        self.browserRequest(browser, 1)

    # 分页请求
    def browserRequest(self, browser, nextClick=None):
        print "SZ深证股票列表爬虫正在爬取页码:", nextClick
        # nextClick != undefined表示还有下一页数据
        if nextClick != 'undefined':
            # nextClick != 1，说明是第一次爬取，不需要触发下一页button的click事件
            if nextClick != 1:
                # 触发下一页button的click事件
                nextNode = "$('input.cls-navigate-next').click()"
                browser.runjs(nextNode)
            else:
                clickNode = "$('div.cls-title-deselected').first().click()"
                browser.runjs(clickNode)
            try:
                # 等待5秒钟，待页面渲染完毕，有可能5秒钟还不够，需要测试，有可能5秒钟太长
                browser.wait_load(3)
            except:
                print 'SZ深证股票列表爬虫，我也不知道是什么异常，反正不影响运行就行'
            # 解析html页面，提取需要的数据
            self.parseData(browser)
        # else分支，nextClick == 'undefined'，说明没有数据可爬取，关闭数据库连接
        else:
            self.dbService.close()
            print 'SZ深证股票列表爬虫，Done'

    # 解析html页面上的数据
    def parseData(self, browser):
        # 完整的html页面字符串
        body = str(browser.html)
        # 使用美丽汤BeautifulSoup工具解析提取数据
        soup = BeautifulSoup(body, 'html.parser')
        # 下面注释的代码可以将html字符串保存为一个html文件，供分析使用
        with open('sz_stock_info.html', 'w') as f:
            f.write(soup.prettify())
        # 找到页面上主要的数据区域，表格区域
        js_tableT01 = soup.find('span', id="REPORT_ID_1110")
        # 获取数据表格
        all_table = js_tableT01.find('table').find('tbody').find('tr').find('td').find_all('table', recursive=False)
        tdclickable = all_table[3]
        # 获取分页
        pagetable = all_table[4]
        # 获取表格中的tbody
        tbody = tdclickable.find('tbody')
        # 获取tbody中的tr
        trs = tbody.find_all('tr')
        items = []
        # 遍历tr
        for tr in trs:
            # 每个tr中的td
            tds = tr.find_all('td')
            # 遍历td
            if tds:
                tda = tds[0].find('a')
                compCode = tda.find('u').get_text().strip()
                compUrl = 'http://www.szse.cn/' + tda['href']
                compName = tds[1].find('u').get_text().strip()
                securityCode = tds[2].get_text().strip()
                securityName = tds[3].get_text().strip()
                theDate = tds[4].get_text().strip()
                wholeCapital = float(int(tds[5].get_text().strip().replace(',', ''))/10000)
                circulatingCapital = float(int(tds[6].get_text().strip().replace(',', ''))/10000)
                announcementUrl = tds[1].find('a')['href'].strip()

                item = StockbaseinfospiderItem()
                item['compCode'] = compCode
                item['compUrl'] = compUrl
                item['compName'] = compName
                item['securityCode'] = securityCode
                item['exchange'] = self.exchange
                item['securityName'] = securityName
                # 测试发现有些时间数据为-，导致插入数据库异常
                if theDate == '-':
                    theDate = '1970-01-01'
                item['theDate'] = theDate
                item['wholeCapital'] = wholeCapital
                item['circulatingCapital'] = circulatingCapital
                item['announcementUrl'] = announcementUrl
                items.append(item)
        # 批量插入数据库
        self.dbService.process_items(items)

        # 获取分页的button
        button = pagetable.find('input', attrs={"name": "navigatebutton", "class": "cls-navigate-next"})
        # 下一页的页码
        nextPageNum = 'undefined'
        if button:
            nextPageNum = button['onclick'].strip()
            if nextPageNum == '':
                nextPageNum = 'undefined'
            else:
                pageSplit = nextPageNum.split(',')
                nextPageNum = pageSplit[2]
        else:
            nextPageNum = 'undefined'
        # 由于页面是异步加载，无刷新分页，所以只能使用spynner触发下一页button的click事件，等待页面加载完毕，继续解析，下面是触发下一次分页操作
        self.browserRequest(browser, nextPageNum)