# MIT—线性代数笔记19 行列式公式和代数余子式

> **作者**: 三少爷的键  
> **来源**: [https://zhuanlan.zhihu.com/p/45879034](https://zhuanlan.zhihu.com/p/45879034)  
> **日期**: 2026-02-12

---

## 第19讲 [行列式](https://zhida.zhihu.com/search?content_id=9257420&content_type=Article&match_order=1&q=%E8%A1%8C%E5%88%97%E5%BC%8F&zhida_source=entity)公式和[代数余子式](https://zhida.zhihu.com/search?content_id=9257420&content_type=Article&match_order=1&q=%E4%BB%A3%E6%95%B0%E4%BD%99%E5%AD%90%E5%BC%8F&zhida_source=entity)

Determinant formulas and cofactors

我们已经认识到了行列式的性质，应该推导出其公式了。[网易公开课](https://link.zhihu.com/?target=http%3A//open.163.com/newview/movie/free%3Fpid%3DM6V0BQC4M%26mid%3DM6V2APP34)我们已经认识到了行列式的性质，应该推导出其公式了。

- **行列式公式 Formula for the determinant**

行列式有如下三个性质：

1. det（***I***)=1。

2. 如果交换行列式的两行，则行列式的数值会反号。

3. 行列式是“矩阵的行”的线性函数。

从这三条性质可以推导出后续的七条性质，从这十个性质出发可以得到二阶方阵的行列式公式：

$$
\begin{array}{llllllllllllllllllll} {\left| {\begin{array}{cccccccccccccccccccc} a&b\\ c&d \end{array}} \right|}&{{=}\left| {\begin{array}{cccccccccccccccccccc} a&0\\ c&d \end{array}} \right|{+}\left| {\begin{array}{cccccccccccccccccccc} 0&b\\ c&d \end{array}} \right|}\\ {}&{{\rm{ = }}\left| {\begin{array}{cccccccccccccccccccc} a&0\\ c&0 \end{array}} \right|{\rm{ + }}\left| {\begin{array}{cccccccccccccccccccc} a&0\\ 0&d \end{array}} \right|{\rm{ + }}\left| {\begin{array}{cccccccccccccccccccc} 0&b\\ c&0 \end{array}} \right|{\rm{ + }}\left| {\begin{array}{cccccccccccccccccccc} 0&b\\ 0&d \end{array}} \right|}\\ {}&{=0 + ad - bc + 0}\\ {}&{ = ad - bc} \end{array}
$$

通过性质3对n阶矩阵的行列式进行拆分，我们可以得到所有只包含n个非零元素的行列式，对于二阶行列式我们从1个拆分为2个，然后拆分成4个。而对于三阶矩阵我们从1个拆分成3个，然后拆分成9个，最后要拆分成27个。但最终这些行列式中有很大一部分等于0。

$$
\begin{array}{llllllllllllllllllll} {\left| {\begin{array}{cccccccccccccccccccc} {{a_{11}}}&{{a_{12}}}&{{a_{13}}}\\ {{a_{21}}}&{{a_{22}}}&{{a_{23}}}\\ {{a_{31}}}&{{a_{32}}}&{{a_{33}}} \end{array}} \right|}&{{\rm{ = }}\left| {\begin{array}{cccccccccccccccccccc} {{a_{11}}}&0&0\\ 0&{{a_{22}}}&0\\ 0&0&{{a_{33}}} \end{array}} \right|{\rm{ + }}\left| {\begin{array}{cccccccccccccccccccc} {{a_{11}}}&0&0\\ 0&0&{{a_{23}}}\\ 0&{{a_{32}}}&0 \end{array}} \right|{\rm{ + }}\left| {\begin{array}{cccccccccccccccccccc} 0&{{a_{12}}}&0\\ {{a_{21}}}&0&0\\ 0&0&{{a_{33}}} \end{array}} \right|}\\ {}&{{\rm{ + }}\left| {\begin{array}{cccccccccccccccccccc} 0&{{a_{12}}}&0\\ 0&0&{{a_{23}}}\\ {{a_{31}}}&0&0 \end{array}} \right|{\rm{ + }}\left| {\begin{array}{cccccccccccccccccccc} 0&0&{{a_{13}}}\\ {{a_{21}}}&0&0\\ 0&{{a_{32}}}&0 \end{array}} \right|{\rm{ + }}\left| {\begin{array}{cccccccccccccccccccc} 0&0&{{a_{13}}}\\ 0&{{a_{22}}}&0\\ {{a_{31}}}&0&0 \end{array}} \right|}\\ {}&{{\rm{ = }}{a_{11}}{a_{22}}{a_{33}} - {a_{11}}{a_{23}}{a_{33}} - {a_{12}}{a_{21}}{a_{33}}}\\ {}&{ + {a_{12}}{a_{23}}{a_{31}} + {a_{13}}{a_{21}}{a_{32}} - {a_{13}}{a_{22}}{a_{31}}} \end{array}
$$

每一个拆分出来的非0行列式都是在每行每列都有且只有一个元素，就如同[置换矩阵](https://zhida.zhihu.com/search?content_id=9257420&content_type=Article&match_order=1&q=%E7%BD%AE%E6%8D%A2%E7%9F%A9%E9%98%B5&zhida_source=entity)的元素分布。应用性质3可以将元素从行列式中提出来，而置换矩阵的行列式值为+1或者-1，因此可以给出行列式的公式。n阶拆分矩阵非0行列式的个数的计算方法就如同计算置换矩阵的个数一样，第一行放置一个非0元素的位置有n个选择，第二行为n-1个……。最后得到共n!个矩阵。

对于拆分得到的三阶矩阵，元素从上至下朝向右侧方向的，其行列式的数值为正，朝向左侧方向的则为负。但是这个规律只适用于三阶矩阵，不适用于高阶矩阵。

![](images/19fe157f1aca.jpg)

行列式的公式： 

$$
\det (\boldsymbol{A}) = \sum\limits_{n!} { \pm {a_{1\alpha }}} {a_{2\beta }}{a_{3\gamma }} \cdots {a_{n\omega }}
$$

其中列标号（ $\alpha$ , $\beta$ , $\gamma$ ……）是列标号（1, 2, 3……n）的某个排列。比如说对于单位阵而言，只有$\alpha$ =1, $\beta$ =2…… $\omega$ =n所得到的行列式为+1，其它都为零，所以单位阵的行列式为1。

例如： 

$$
\left| {\begin{array}{cccccccccccccccccccc} 0&0&1&1\\ 0&1&1&0\\ 1&1&0&0\\ 1&0&0&1 \end{array}} \right| = \left| {\begin{array}{cccccccccccccccccccc} 0&0&0&1\\ 0&0&1&0\\ 0&1&0&0\\ 1&0&0&0 \end{array}} \right| + \left| {\begin{array}{cccccccccccccccccccc} 0&0&1&0\\ 0&1&0&0\\ 1&0&0&0\\ 0&0&0&1 \end{array}} \right|
$$

列标号取（4,3,2,1）得到第一个拆分行列式，符号为正，因为只要经过两次交换就能变为（1,2,3,4）。第二个为（3,2,1,4），因为只需交换一次就可变为正序，所以符号为负。因此本行列式为0。

- **代数余子式 Cofactor formula**

代数余子式是用较小的矩阵的行列式来写出n阶行列式的公式。

det（***A***）= 

$$
{a_{11}}({a_{22}}{a_{33}} - {a_{23}}{a_{32}}) + {a_{12}}( - {a_{21}}{a_{33}} + {a_{23}}{a_{31}} + {a_{13}}{a_{21}}{a_{32}} - {a_{22}}{a_{31})}
$$

= 

$$
\left| {\begin{array}{cccccccccccccccccccc} {{a_{11}}}&0&0\\ 0&{{a_{22}}}&{{a_{23}}}\\ 0&{{a_{32}}}&{{a_{33}}} \end{array}} \right| + \left| {\begin{array}{cccccccccccccccccccc} 0&{{a_{12}}}&0\\ {{a_{21}}}&0&{{a_{23}}}\\ {{a_{31}}}&0&{{a_{33}}} \end{array}} \right| + \left| {\begin{array}{cccccccccccccccccccc} 0&0&{{a_{13}}}\\ {{a_{21}}}&{{a_{22}}}&0\\ {{a_{31}}}&{{a_{32}}}&0 \end{array}} \right|
$$

将原公式中属于矩阵第一行的a1j提出来，其系数即为代数余子式，是一个低阶行列式的值。这个低阶行列式是由原矩阵去掉a1j所在的行和列组成的。

对矩阵中任意元素aij而言，其代数余子式Cij就是矩阵的行列式的公式中aij的系数。Cij等于原矩阵移除第i行和第j列后剩余元素组成的n-1阶矩阵的行列式数值乘以 $(-1)^{i+j}$ 。（Cij在i+j为偶数时为正，奇数时为负数。）

对于n阶方阵，其行列式的代数余子式公式为：

det（***A***）= 

$$
{a_{11}}{{\rm{C}}_{11}}{\rm{ + }}{a_{12}}{{\rm{C}}_{12}}{\rm{ + }} \cdots {\rm{ + }}{a_{1{\rm{n}}}}{{\rm{C}}_{1{\rm{n}}}}
$$

对于二阶矩阵，按照代数余子式公式则有 

$$
\left| {\begin{array}{cccccccccccccccccccc} a&b\\ c&d \end{array}} \right| = ad + b( - c)
$$

对于矩阵行列式的计算，消元的得到主元是一个很好的方法，与之相比行列式的展开公式较为复杂，而代数余子式的方法介于两者之间，它的核心想法是通过降阶来将原来的行列式展开成更简单的行列式。

举"[三对角阵](https://zhida.zhihu.com/search?content_id=9257420&content_type=Article&match_order=1&q=%E4%B8%89%E5%AF%B9%E8%A7%92%E9%98%B5&zhida_source=entity)"（tridiagonal matrix）为例，它除了对角线和对角线两侧相邻的元素之外，其它元素均为0。例如由1组成的4阶三对角阵为 

$$
{\boldsymbol{A}_4} = \left[ {\begin{array}{cccccccccccccccccccc} 1&1&0&0\\ 1&1&1&0\\ 0&1&1&1\\ 0&0&1&1 \end{array}} \right]
$$

由1组成的n阶三对角阵的行列式等于多少？

我们可以从1阶开始算起： 

$$
\left| {{\boldsymbol{A}_1}} \right| = 1
$$

 , 

$$
\left| {{\boldsymbol{A}_2}} \right| = \left| {\begin{array}{cccccccccccccccccccc} 1&1\\ 1&1 \end{array}} \right| = 0
$$

 ， 

$$
\left| {{\boldsymbol{A}_3}} \right| = \left| {\begin{array}{cccccccccccccccccccc} 1&1&0\\ 1&1&1\\ 0&1&1 \end{array}} \right| =- 1
$$

 ，则有 

$$
\left| {{\boldsymbol{A}_4}} \right| = 1\left| {\begin{array}{cccccccccccccccccccc} 1&1&0\\ 1&1&1\\ 0&1&1 \end{array}} \right|{\rm{ - }}1\left| {\begin{array}{cccccccccccccccccccc} 1&1&0\\ 0&1&1\\ 0&1&1 \end{array}} \right| = \left| {{\boldsymbol{A}_3}} \right| - 1\left| {{\boldsymbol{A}_2}} \right| =  - 1
$$

从矩阵的特殊结构我们可以得到： 

$$
\left| {{\boldsymbol{A}_{\rm{n}}}} \right| = \left| {{\boldsymbol{A}_{{\rm{n - }}1}}} \right| - 1\left| {{\boldsymbol{A}_{{\rm{n - 2}}}}} \right|
$$

由1组成的n阶三对角阵的行列式从1阶开始按照1,0，-1，-1,0,1进行循环。
