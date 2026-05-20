Python
月份与产品类别环比分析-EXC-0-4-699d783a-代码
代码已被收起
import pandas as pd

# 读取清洗后的伦敦数据
cleaned_file_path = '/home/notebook/d5mmv1tvjqnknq13t1u7ex4rn/英国餐厅销售数据清洗后.xlsx'
uk_df = pd.read_excel(cleaned_file_path)

# 添加月份字段
uk_df['Month'] = uk_df['Date'].dt.month

# 按月份和产品类别分析销售额
monthly_category_sales = uk_df.groupby(['Month', 'Product'])['Sales'].sum().unstack(fill_value=0)
print("按月份和产品类别的销售额分布:")
print(monthly_category_sales)
print()

# 计算11月到12月的环比变化率
month_11_sales = uk_df[uk_df['Month'] == 11].groupby('Product')['Sales'].sum()
month_12_sales = uk_df[uk_df['Month'] == 12].groupby('Product')['Sales'].sum()

monthly_change = ((month_12_sales - month_11_sales) / month_11_sales * 100).fillna(0)
print("11月到12月各产品类别的销售额环比变化率:")
print(monthly_change.round(2))
print()

# 按月份统计各类别销售额占比
monthly_category_percentage = uk_df.groupby(['Month', 'Product'])['Sales'].sum().groupby(level=0).apply(lambda x: x / x.sum() * 100).unstack(fill_value=0)
print("各月份内产品类别的销售占比:")
print(monthly_category_percentage.round(2))

# 各产品类别11月至12月销售额环比增长率柱状图，直观展示不同品类的销售增长幅度，突出Burgers等高增长品类。
import pandas as pd
import matplotlib.pyplot as plt
import numpy as np

# 设置中文字体和颜色循环
custom_colors = [
    "#A6ADFC", "#3C3F5F", "#CEB6FC", "#38A39F",
    "#9ED9ED", "#84909C", "#E0F2C0", "#2D80B4",
    "#9FCBF5", "#827C68", "#EBD6E9", "#733D72"
]
plt.rcParams['axes.prop_cycle'] = plt.cycler(color=custom_colors)
plt.rcParams['font.sans-serif'] = ['Alibaba PuHuiTi 3.0']
plt.rcParams['axes.unicode_minus'] = False

# 读取清洗后的伦敦数据
cleaned_file_path = '/home/notebook/d5mmv1tvjqnknq13t1u7ex4rn/英国餐厅销售数据清洗后.xlsx'
uk_df = pd.read_excel(cleaned_file_path)

# 添加月份字段
uk_df['Month'] = uk_df['Date'].dt.month

# 计算11月到12月的环比变化率
month_11_sales = uk_df[uk_df['Month'] == 11].groupby('Product')['Sales'].sum()
month_12_sales = uk_df[uk_df['Month'] == 12].groupby('Product')['Sales'].sum()

monthly_change = ((month_12_sales - month_11_sales) / month_11_sales * 100).fillna(0)
monthly_change_sorted = monthly_change.sort_values(ascending=False)

# 创建柱状图
plt.figure(figsize=(12, 7))

# 为不同的柱子分配不同的颜色以突出重点
bars = plt.bar(range(len(monthly_change_sorted)), monthly_change_sorted.values, 
               color=[custom_colors[0] if product == 'Burgers' else custom_colors[3] for product in monthly_change_sorted.index])

plt.xlabel('产品类别', fontsize=12)
plt.ylabel('销售额环比增长率 (%)', fontsize=12)
plt.title('各产品类别11月至12月销售额环比增长率', fontsize=16, pad=20)

# 设置x轴标签
plt.xticks(range(len(monthly_change_sorted)), monthly_change_sorted.index, rotation=45, ha='right')

# 在柱子上添加数值标签
for i, v in enumerate(monthly_change_sorted.values):
    plt.text(i, v + max(monthly_change_sorted.values) * 0.01, f'{v:.2f}%', 
             ha='center', va='bottom', fontsize=10)

# 添加网格线提升可读性
plt.grid(axis='y', linestyle='--', alpha=0.7)

# 调整布局避免标签截断
plt.tight_layout()

# 显示图形
plt.show()
展开/收起
按月份和产品类别的销售额分布:
Product   Beverages     Burgers  Chicken Sandwiches       Fries  Sides & Other
Month                                                                         
11       12600.0105  30600.0234           12000.297  15199.9621       5999.976
12       16200.0725  71200.2684           20000.495  19399.9677       7999.968

11月到12月各产品类别的销售额环比变化率:
Product
Beverages              28.57
Burgers               132.68
Chicken Sandwiches     66.67
Fries                  27.63
Sides & Other          33.33
Name: Sales, dtype: float64

各月份内产品类别的销售占比:
Product      Beverages  Burgers  Chicken Sandwiches  Fries  Sides & Other
Month Month                                                              
11    11         16.49    40.05               15.71  19.90           7.85
12    12         12.02    52.82               14.84  14.39           5.93

各产品类别在2024年11月至12月期间的销售额环比增长率中，Burgers类别以132.68%的增长率遥遥领先，显著高于其他品类；Chicken Sandwiches增长率为66.67%，位居第二；Sides & Other为33.33%，Beverages为28.57%，Fries为27.63%。Burgers的增长率是Fries的近5倍，表明其在该时间段内表现出极强的销售动能，可能与节日促销或新品推出有关。所有品类均呈现正向增长，说明整体业务在年末有明显提升。
进行购买渠道与产品类别的交叉分析
探究线上与得来速渠道在核心品类销售结构上的差异。

Python
渠道与产品类别交叉分析-EXC-0-4-3d891b22-代码
代码已被收起
# 购买渠道与产品类别的交叉分析
channel_product_analysis = pd.crosstab(
    uk_df['Purchase Type'], 
    uk_df['Product'], 
    values=uk_df['Sales'], 
    aggfunc='sum'
)

print("购买渠道与产品类别的销售额交叉分析:")
print(channel_product_analysis)
print()

# 计算各渠道内各类别销售额占比
channel_product_pct = uk_df.groupby('Purchase Type').apply(
    lambda x: x.groupby('Product')['Sales'].sum() / x['Sales'].sum() * 100
).unstack(fill_value=0)

print("各渠道内产品类别的销售占比 (%):")
print(channel_product_pct.round(2))
print()

# 按渠道分析各类别的平均销售额
channel_product_avg = uk_df.groupby(['Purchase Type', 'Product'])['Sales'].mean().unstack(fill_value=0)
print("各渠道内各类别的平均销售额:")
print(channel_product_avg.round(2))

# 各购买渠道（Online vs Drive-thru）内不同产品类别的销售额占比堆叠柱状图，用于对比销售渠道的产品结构差异
import pandas as pd
import matplotlib.pyplot as plt
import numpy as np

# 设置自定义颜色循环
custom_colors = [
    "#A6ADFC", "#3C3F5F", "#CEB6FC", "#38A39F",
    "#9ED9ED", "#84909C", "#E0F2C0", "#2D80B4",
    "#9FCBF5", "#827C68", "#EBD6E9", "#733D72"
]
plt.rcParams['axes.prop_cycle'] = plt.cycler(color=custom_colors)

# 设置字体
plt.rcParams['font.sans-serif'] = ['Alibaba PuHuiTi 3.0']
plt.rcParams['axes.unicode_minus'] = False

# 读取清洗后的伦敦数据
cleaned_file_path = '/home/notebook/d5mmv1tvjqnknq13t1u7ex4rn/英国餐厅销售数据清洗后.xlsx'
uk_df = pd.read_excel(cleaned_file_path)

# 重新计算各渠道内各类别销售额占比
channel_product_sales = uk_df.groupby(['Purchase Type', 'Product'])['Sales'].sum().unstack(fill_value=0)
channel_total_sales = channel_product_sales.sum(axis=1)
channel_product_pct = channel_product_sales.div(channel_total_sales, axis=0) * 100

# 确保所有的产品类别都在列中
all_products = sorted(uk_df['Product'].unique())
channel_product_pct = channel_product_pct.reindex(columns=all_products, fill_value=0)

print("各渠道产品销售占比数据:")
print(channel_product_pct)
print("\n数据形状:", channel_product_pct.shape)

# 准备绘图数据
categories = channel_product_pct.columns.tolist()
channels = channel_product_pct.index.tolist()

# 绘制堆叠柱状图
fig, ax = plt.subplots(figsize=(12, 8))

bottom = np.zeros(len(channels))
colors = custom_colors[:len(categories)]

# 创建堆叠柱状图
for i, category in enumerate(categories):
    values = channel_product_pct[category].values
    ax.bar(channels, values, bottom=bottom, label=category, color=colors[i])
    bottom += values

# 设置图形属性
ax.set_xlabel('购买渠道', fontsize=12)
ax.set_ylabel('销售额占比 (%)', fontsize=12)
ax.set_title('各购买渠道内不同产品类别的销售额占比堆叠柱状图', fontsize=16, pad=20)
ax.legend(title='产品类别', bbox_to_anchor=(1.05, 1), loc='upper left')

# 在柱子上添加百分比标签
bottom = np.zeros(len(channels))
for i, category in enumerate(categories):
    values = channel_product_pct[category].values
    for j, (value, ch) in enumerate(zip(values, channels)):
        if value > 0:  # 只对大于0的值添加标签
            ax.text(j, bottom[j] + value/2, f'{value:.1f}%', 
                   ha='center', va='center', fontsize=9, color='white' if value > 5 else 'black')
    bottom += values

plt.xticks(rotation=0)
plt.tight_layout()
plt.show()
展开/收起
购买渠道与产品类别的销售额交叉分析:
Product        Beverages     Burgers  Chicken Sandwiches       Fries  \
Purchase Type                                                          
Drive-thru      4399.984  11799.9861           6000.1485   4399.9826   
Online         24400.099  90000.3057          26000.6435  30199.9472   

Product        Sides & Other  
Purchase Type                 
Drive-thru          1999.992  
Online             11999.952  

各渠道内产品类别的销售占比 (%):
Product             Purchase Type
Beverages           Drive-thru       15.38
                    Online           13.36
Burgers             Drive-thru       41.26
                    Online           49.29
Chicken Sandwiches  Drive-thru       20.98
                    Online           14.24
Fries               Drive-thru       15.38
                    Online           16.54
Sides & Other       Drive-thru        6.99
                    Online            6.57
dtype: float64

各渠道内各类别的平均销售额:
Product        Beverages  Burgers  Chicken Sandwiches    Fries  Sides & Other
Purchase Type                                                                
Drive-thru       2199.99  5899.99             2000.05  2199.99         1000.0
Online           2033.34  6923.10             2000.05  2157.14         1000.0
各渠道产品销售占比数据:
Product        Beverages    Burgers  Chicken Sandwiches      Fries  \
Purchase Type                                                        
Drive-thru     15.384509  41.258558           20.979472  15.384504   
Online         13.362526  49.287973           14.239052  16.538768   

Product        Sides & Other  
Purchase Type                 
Drive-thru          6.992956  
Online              6.571681  

数据形状: (2, 5)

在Drive-thru渠道中，Burgers销售额占比最高，达41.3%，其次是Chicken Sandwiches（21.0%）和Fries（15.4%），Beverages占比为15.4%，Sides & Other占比7.0%；在Online渠道中，Burgers同样占据主导地位，占比49.3%，高于Drive-thru渠道的41.3%，而Chicken Sandwiches占比下降至14.2%，Fries占比上升至16.5%，Beverages占比降至13.4%，Sides & Other占比为6.6%。整体来看，Burgers在两个渠道中均是核心品类，且在线上渠道中占比显著更高，表明线上用户更倾向于购买汉堡类商品；而Chicken Sandwiches在Drive-thru渠道中的占比明显高于线上，显示该品类在得来速场景下更具吸引力。
分析高价值订单的产品共现模式和礼品卡用户的产品偏好
深入探索线上渠道内部产品组合与客单价驱动因素，以及礼品卡高客单价背后的具体产品偏好。

Python
高价值订单和礼品卡用户产品偏好分析-EXC-0-4-d4adbf28-代码
代码已被收起
# 分析高价值订单中的产品共现模式
threshold = uk_df['Sales'].quantile(0.9)  # 90%分位数作为高价值订单阈值
high_value_orders = uk_df[uk_df['Sales'] >= threshold]

print("高价值订单产品分布分析:")
print("高价值订单中各产品类别的出现频次:")
high_value_product_counts = high_value_orders['Product'].value_counts()
print(high_value_product_counts)
print()

print("高价值订单中各产品类别的平均销售额:")
high_value_product_avg_sales = high_value_orders.groupby('Product')['Sales'].mean()
print(high_value_product_avg_sales.round(2))
print()

# 分析礼品卡用户的产品偏好
gift_card_orders = uk_df[uk_df['Payment Method'] == 'Gift Card']

print("礼品卡支付订单的产品分布:")
gift_card_product_dist = gift_card_orders['Product'].value_counts()
print(gift_card_product_dist)
print()

print("礼品卡支付订单中各产品的平均销售额:")
gift_card_product_avg_sales = gift_card_orders.groupby('Product')['Sales'].mean()
print(gift_card_product_avg_sales.round(2))
print()

# 比较礼品卡与其他支付方式的产品偏好
payment_product_comparison = uk_df.groupby(['Payment Method', 'Product'])['Sales'].agg(['sum', 'mean', 'count']).round(2)
print("按支付方式和产品类别的综合分析:")
print(payment_product_comparison)
print()

# 计算礼品卡在高价值订单中的产品分布
gift_card_high_value_orders = high_value_orders[high_value_orders['Payment Method'] == 'Gift Card']
print("礼品卡高价值订单的产品分布:")
print(gift_card_high_value_orders['Product'].value_counts())
展开/收起
高价值订单产品分布分析:
高价值订单中各产品类别的出现频次:
Product
Burgers    8
Name: count, dtype: int64

高价值订单中各产品类别的平均销售额:
Product
Burgers    7250.03
Name: Sales, dtype: float64

礼品卡支付订单的产品分布:
Product
Fries                 5
Beverages             4
Sides & Other         4
Burgers               4
Chicken Sandwiches    4
Name: count, dtype: int64

礼品卡支付订单中各产品的平均销售额:
Product
Beverages             2050.01
Burgers               7450.02
Chicken Sandwiches    2000.05
Fries                 2160.00
Sides & Other         1000.00
Name: Sales, dtype: float64

按支付方式和产品类别的综合分析:
                                        sum     mean  count
Payment Method Product                                     
Cash           Beverages            2000.01  2000.01      1
               Burgers              7000.05  7000.05      1
               Chicken Sandwiches   2000.05  2000.05      1
               Fries                4399.98  2199.99      2
               Sides & Other        1000.00  1000.00      1
Credit Card    Beverages           18600.05  2066.67      9
               Burgers             65000.14  6500.01     10
               Chicken Sandwiches  22000.54  2000.05     11
               Fries               19399.97  2155.55      9
               Sides & Other        8999.96  1000.00      9
Gift Card      Beverages            8200.03  2050.01      4
               Burgers             29800.10  7450.02      4
               Chicken Sandwiches   8000.20  2000.05      4
               Fries               10799.98  2160.00      5
               Sides & Other        3999.98  1000.00      4

礼品卡高价值订单的产品分布:
Product
Burgers    4
Name: count, dtype: int64
目标4 洞察
线上渠道（Online）是绝对核心销售来源，贡献了86.46%的销售额。数据显示，线上订单共64笔，总销售额达182,600.95，平均客单价为2,853.14；相比之下，得来速（Drive-thru）仅贡献13.54%的销售额（28,600.09），且样本量较小（11笔）。尽管两者客单价差异不大（线上略高约5%），但线上渠道在订单规模上占据压倒性优势，表明伦敦顾客高度依赖数字化点餐服务。来源
信用卡是主流支付手段，但礼品卡在驱动高额消费上表现突出。整体来看，信用卡支付占比最高（63.45%销售额，48笔订单），是基础流量支撑；然而，礼品卡虽然订单数较少（21笔），却贡献了28.79%的销售额，且拥有最高的平均客单价（2,895.25），高于信用卡（2,791.68）和现金（2,733.35）。这暗示礼品卡用户具有更强的购买力或更倾向于批量/高价值采购。来源
支付偏好与购买渠道存在强结构性关联：得来速仅接受信用卡，而线上渠道呈现多元化支付特征。交叉分析显示，100%的得来速订单使用信用卡支付，现金和礼品卡在该渠道的使用率为0%。相反，线上渠道中信用卡占比57.72%，礼品卡占比33.3%，现金占比8.98%。这意味着得来速场景下的支付选择极度单一，可能限制了部分习惯使用现金或礼品卡的潜在顾客转化。来源
高价值订单（Top 10%，阈值>6,920.03）完全集中于线上渠道，且礼品卡使用比例显著倒挂。在所有8笔高价值订单中，100%来自线上渠道。更值得注意的是，在高价值订单中，礼品卡支付占比高达50%（4笔），远超其在整体订单中的占比（28%）；信用卡占比37.5%，现金占比12.5%。这一反常现象进一步证实礼品卡是撬动大额交易的关键杠杆，建议针对礼品卡用户设计专属的高客单价促销组合。来源
线上渠道占据绝对主导地位，且是高价值订单的唯一来源
论据：线上渠道（Online）贡献了 86.46% 的总销售额（182,600.95），订单量占比高达 85.33%（64单 vs 得来速11单）。更为关键的是，定义的高价值订单（Top 10%，阈值 > 6,920.03）100% 集中在线上渠道，得来速渠道无任何高价值订单产生。
洞察：伦敦市场的消费重心已完全向线上转移，得来速仅作为补充性低频场景存在。高客单价与大额交易完全依赖线上场景驱动，建议将核心营销资源、新品首发及高价值套餐推荐策略全面倾斜至线上平台，而来得速渠道应侧重于标准化、便捷性的基础服务优化。来源 相关文件: 英国餐厅销售数据清洗后.xlsx
礼品卡是驱动高客单价的核心支付工具，与高额汉堡消费强关联
论据：礼品卡（Gift Card）虽仅占订单数的 28%，但其平均客单价最高，达 2,895.25，显著高于信用卡（2,791.68）和现金（2,733.35）。在高价值订单中，礼品卡支付占比高达 50%（4/8单）。进一步下钻发现，礼品卡支付订单中，Burgers 的平均销售额高达 7,450.02，远超其他品类；且所有礼品卡支付的高价值订单均包含 Burgers。
洞察：礼品卡用户呈现出显著的“高净值、大份量”特征，极可能对应团队聚餐或家庭囤货场景，且汉堡是此类大额消费的核心载体。建议针对礼品卡用户设计“汉堡+配菜”的大份量专属套餐，或在礼品卡充值环节绑定汉堡类优惠券，以进一步拉升客单价并锁定高频复购。来源 相关文件: 英国餐厅销售数据清洗后.xlsx
Burgers呈现强劲的季节性增长爆发力，是12月销售增长的核心引擎
论据：从11月到12月，全品类销售额均有增长，但 Burgers 的环比增长率高达 132.68%（从11月的30,600.02增至12月的71,200.27），远超Chicken Sandwiches（66.67%）、Sides & Other（33.33%）及Beverages/Fries（约28%）。在12月的销售结构中，Burgers占比提升至 52.82%，成为超过半壁江山的核心品类。
洞察：Burgers具有极强的季节性爆发特征，可能在冬季或节假日期间更受青睐。12月的业绩增长主要由Burgers驱动，表明该品类是应对季节性波动的关键抓手。建议在后续类似季节节点前，提前储备Burgers相关库存，并围绕Burgers策划节日主题营销活动，以最大化利用其自然增长势能。来源 相关文件: 英国餐厅销售数据清洗后.xlsx
渠道间产品结构差异显著：线上侧重汉堡，得来速侧重三明治与饮料
论据：在线上渠道中，Burgers 的销售占比最高，达 49.29%；而在得来速（Drive-thru）渠道中，Burgers占比为 41.26%，但 Chicken Sandwiches（20.98% vs 线上14.24%）和 Beverages（15.38% vs 线上13.36%）的相对占比更高。此外，得来速渠道完全不支持现金以外的非信用卡支付（现金占比0%，信用卡100%），而线上渠道支付方式更多元（信用卡57.72%，礼品卡33.3%，现金8.98%）。
洞察：不同渠道的用户偏好存在结构性差异。线上用户更倾向于购买核心主食（Burgers）并搭配多元支付（尤其是礼品卡），适合推广复杂套餐；得来速用户更偏好便捷拿取的三明治和饮料，且支付习惯单一（仅信用卡）。建议在线上菜单强化“汉堡+多品组合”的推荐算法，而在得来速菜单优化“三明治+饮料”的快速通行组合，以契合各自场景下的用户决策逻辑。来源 相关文件: 英国餐厅销售数据清洗后.xlsx
