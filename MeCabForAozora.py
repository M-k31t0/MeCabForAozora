import sys
import re
import os
import zipfile
import requests
import os.path
import glob
import subprocess
from bs4 import BeautifulSoup
from typing import Union
import MeCab
import neologdn


def get_work_info(work_url, target_pattern):
    try:
        response = requests.get(work_url)
        get_info = []
        soup = BeautifulSoup(response.content, 'html.parser')
        # 作品名取得
        body_font = soup.find_all('font')
        match = re.search(target_pattern[0], str(body_font))
        if match:
            matched = match.group()
            matched = re.sub(">", "", matched)
            matched = re.sub("</", "", matched)
            get_info.append(matched)
        else:
            get_info.append(None)
        # 作者名取得
        match = re.search(target_pattern[1], str(body_font))
        if match:
            match = match.group()
            match = re.sub('l">', "", match)
            match = re.sub("</a>", "", match)
            get_info.append(match)
        else:
            get_info.append(None)
        # ZIPファイル名を取得
        body_a = soup.find_all('a')
        match = re.search(target_pattern[2], str(body_a))
        if match:
            get_info.append(match.group())
        else:
            match = re.search(target_pattern[3], str(body_a))
            if match:
                get_info.append(match.group())
            else:
                get_info.append(None)
        # ダウンロードURL取得
        match = re.sub(r'(card)[0-9]*(\.html)', "files/", work_url)
        match += get_info[2]
        get_info.append(match)
        return get_info
    except Exception:
        print("失敗\n")
        print("警告: URLが正しくありません。処理を中断します。")
        sys.exit()


def downloadFile(url: str, target_dir='./') -> Union[str, bool]:
    filename = target_dir + url.split('/')[-1]
    r = requests.get(url, stream=True)
    with open(filename, 'wb') as f:
        for chunk in r.iter_content(chunk_size=1024):
            if chunk:
                f.write(chunk)
                f.flush()
        return filename
    return False


def unzip(filename: str, target_dir='./') -> list:
    if not zipfile.is_zipfile(filename):
        print('警告: {}は.zipではありません'.format(filename))
        raise Exception
    zfile = zipfile.ZipFile(filename)
    zfile.extractall(target_dir)
    zfile.close()
    target_dir = re.sub('./', '', target_dir)
    dst_filenames = glob.glob(target_dir + '/' + '*.txt')
    # dst_filenames = [filename for filename in txt_files if not filename.endswith("_splited.txt")]
    return dst_filenames


def readSjis(path: str) -> str:
    with open(path, mode="r", encoding='shift_jis') as f:
        text = f.read()
    return text


def txtConverter(filenames, text):
    # 前処理
    try:
        text = re.split(r"\-{5,}", text)[2]  # ハイフンより上を削除
        text = re.split(r"底本：", text)[0]  # 「底本：」より下を削除
        text = re.sub(r"［＃[０-９]+字下げ.*?中見出し］", "", text)  # 中見出しを削除
        text = re.sub("※", "", text)  # 「※」を削除
        text = re.sub(r"《.*?》", "", text)  # 《...》を削除
        text = re.sub(r"［.*?］", "", text)  # ［...］を削除
        text = re.sub(r"（.*?）", "", text)  # （...）を削除
        text = re.sub(r"｜", "", text)  # 「｜」を削除
        text = re.sub("\n", "", text)  # 改行を削除
        text = re.sub("　　[一二三四五六七八九十]+", "", text)  # 漢数字を削除
        text = re.sub(r"\u3000", "", text)  # 全角スペースを削除
        text = re.sub(r"。", "<period>", text)  # 句点を<period>に
        # neologdnによる処理
        text = neologdn.normalize(text)
        # 「」内の<period>を句点に置換
        pattern = re.compile("「.*?」")
        match_sents = pattern.findall(text)
        for i, m_sent in enumerate(match_sents):
            new_sent = m_sent.replace("<period>", "。")
            text = text.replace(m_sent, new_sent)
        # <period>で分割
        text_splitted = text.split("<period>")
        # 空要素を取り除く
        text_splitted = list(filter(None, text_splitted))

        # １文ずつ形態素解析
        # mecab = MeCab.Tagger("-Owakati")
        mecab = MeCab.Tagger(
            r'-Owakati -r "MeCab\\etc\\mecabrc" -d "MeCab\\dic\\ipadic" -u "MeCab\\dic\\NEologd\\NEologd.20200910-u.dic"')
        for i in range(len(text_splitted)):
            text_splitted[i] = mecab.parse(text_splitted[i]).split()
        # テキストファイルに書き込む
        filenames = re.sub(".txt", "", filenames)
        file_w = filenames + "_splitted.txt"
        s = ""
        with open(file_w, mode="w", encoding="utf-8") as f:
            for text in text_splitted:
                s += " ".join(text) + " 。 " + "\n"
            f.write(s[0:-1])

        print("変換処理が完了しました。")
        print("出力ファイルパス: \{}".format(file_w))
        print("変換後の行数: %d" % (len(s.split("\n"))-1))
        print("単語種類数/全単語数: %d/%d" % (len(set(s.split())), len(s.split())))
        # print("1行あたりの平均単語数: %.1f" % (len(s.split())/len(set(s.split()))))
        return file_w

    except Exception as e:
        print("変換処理に失敗しました。")
        print("警告: テキストファイルの解析ができません。")
        print("エラー内容: {}\n".format(e))
        file_w = None
        return file_w


def yn_input(judge):
    if judge in ['y', 'ye', 'yes']:
        return True


def merge_files(dir_name, s_filepath):
    str_yn = input("\n変換したファイルをマージしますか(y/n)?: ").lower()
    if yn_input(str_yn):
        m_text = ""
        for i in range(len(s_filepath)):
            with open(s_filepath[i], mode="r", encoding='utf-8') as f:
                text = f.read()
            if i != len(s_filepath)-1:
                m_text += text + '\n'
            else:
                m_text += text
        with open('./' + dir_name + '/merged.txt', mode='w', encoding='utf-8') as f:
            f.write(m_text)
        print("{}ファイルを新規ファイルとしてマージしました。".format(len(s_filepath)))
        print("出力ファイルパス: \{}\merged.txt".format(dir_name))
        print("マージ後の行数: %d" % (len(m_text.split("\n"))))


def dir_isfile(dir_name):
    file_name = os.listdir('./' + dir_name)
    file_num = sum(os.path.isfile(os.path.join('./' + dir_name, name))
                   for name in os.listdir('./' + dir_name))
    print("注意: \{} ディレクトリ内に{}ファイル存在します。\n".format(dir_name, file_num))
    print(*file_name, sep='\n')
    str_yn = input("\n続行するには全て削除する必要があります。削除しますか(y/n)?: ").lower()
    if yn_input(str_yn):
        for filename in os.listdir('./' + dir_name):
            file_path = os.path.join('./' + dir_name, filename)
            if os.path.isfile(file_path):
                os.remove(file_path)
        print("{}ファイルを削除しました。\n".format(file_num))
    else:
        raise KeyboardInterrupt


def dir_isdir(dir_name):
    print("警告: \{} が存在しません。".format(dir_name))
    str_yn = input(
        "続行するには {} ディレクトリを作成する必要があります。新規作成しますか(y/n)?: ".format(dir_name)).lower()
    if yn_input(str_yn):
        os.mkdir('./' + dir_name)
        print("{} ディレクトリを作成しました。\n".format(dir_name))
    else:
        raise KeyboardInterrupt


def main():
    dir_name = 'out'    # 作成するディレクトリ名
    zip_file = []
    filenames = []
    URL = []
    info = []
    split_path = []
    i = 1
    j = 0
    target_pattern = [r'(>).*(/)',
                      r'(l">).*(</a>)',
                      r'[0-9]*_ruby_[0-9]*(\.zip)',
                      r'[0-9]*_txt_[0-9]*(\.zip)']
    try:
        print("================================================================================")
        print('Python MeCab for 青空文庫 (MeCabForAozora.exe)'.center(80))
        print("Powered by mecab-ipadic-NEologd".center(80))
        print("================================================================================")

        if not os.path.isdir('./' + dir_name):
            dir_isdir(dir_name)
        if len(os.listdir('./' + dir_name)) > 0:
            dir_isfile(dir_name)

        print("青空文庫の書籍URLを入力してください。'e'で変換処理を開始します。")
        print("入力形式について不明な場合は'help'を入力してください。\n")
        while True:
            URL_str = input('URL[{}]: '.format(i))
            if URL_str == 'e':
                break
            if URL_str == 'help':
                print(
                    "--------------------------------------------------------------------------------")
                print("青空文庫(https://www.aozora.gr.jp)にアクセスし、書籍ページのURLをコピーします。")
                print("例) 夏目漱石の「こころ」を入力する場合: ")
                print("https://www.aozora.gr.jp/cards/000148/card773.html\n")
                print("注意: 必ず.zip形式のファイルが存在するページURLを入力してください。")
                print(
                    "--------------------------------------------------------------------------------\n")
                continue
            else:
                if not re.search("www.aozora.gr.jp", URL_str):
                    print("警告: 入力したURLが不正です。やり直してください。\n")
                    continue
                print("データ取得中... ", end="")
                info = get_work_info(URL_str, target_pattern)
                print("成功")
                print("作品名: {}".format(info[0]))
                print("著者名: {}".format(info[1]))
                print("テキストファイル(.zip): {}".format(info[2]))
                print("ダウンロードURL: {}".format(info[3]))
                if URL_str not in URL:
                    URL.append(URL_str)
                    zip_file.append(downloadFile(
                        info[3], './' + dir_name + '/'))
                    print('{} をダウンロードしました。'.format(info[2]))
                    filenames = unzip(zip_file[i-1], './' + dir_name)
                    print('{} を解凍しました。\n'.format(info[2]))
                    i += 1
                else:
                    print('警告: {} はすでにダウンロードされています。\n'.format(info[2]))

        for j in range(len(URL)):
            if URL[j] == 'e':
                break
            print("\n")
            print("[{}/{}] ファイルの処理を開始します...".format(j+1, len(URL)))
            print("対象ファイルパス: \{}".format(filenames[j]))
            text = readSjis(filenames[j])
            split_path.append(txtConverter(filenames[j], text))

        if len(URL) > 1:
            merge_files(dir_name, split_path)

    except Exception as e:
        print("\n警告: 例外処理を検出したため終了します。")
        print("エラー内容: {}\n".format(e))

    except KeyboardInterrupt as e:
        print("\n警告: ユーザによって処理が中断されました。\n")

    else:
        print("\nプログラムは正常に終了しました。")

    finally:
        subprocess.call('PAUSE', shell=True)
        sys.exit()


if __name__ == "__main__":
    main()
