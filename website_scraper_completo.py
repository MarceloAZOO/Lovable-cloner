#!/usr/bin/env python3
"""
Website Scraper Completo com Tratamento Avançado de Links e Botões
-----------------------
Este script extrai o código HTML, CSS e JavaScript de qualquer site,
incluindo subpáginas, e organiza os arquivos para hospedagem em outra plataforma.
Inclui tratamento avançado de links e botões para garantir navegação funcional no site extraído.
"""

import os
import sys
import time
import requests
import argparse
from urllib.parse import urljoin, urlparse, urlunsplit
import re
import json
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from concurrent.futures import ThreadPoolExecutor
import logging
import hashlib
import shutil

# Configuração de logging
logging.basicConfig(level=logging.INFO, 
                    format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class WebsiteScraper:
    def __init__(self, base_url, output_dir, max_pages=20, include_subdomains=False):
        """Inicializa o scraper com configurações básicas."""
        self.base_url = base_url
        self.output_dir = output_dir
        self.max_pages = max_pages
        self.include_subdomains = include_subdomains
        
        # Parse da URL base
        self.base_parsed = urlparse(base_url)
        self.base_domain = self.base_parsed.netloc
        
        # Configuração de diretórios
        self.setup_directories()
        
        # Rastreamento de URLs
        self.visited_urls = set()
        self.to_visit_urls = [base_url]
        self.resource_map = {}  # Mapeia URLs originais para caminhos locais
        self.page_map = {}      # Mapeia URLs de páginas para arquivos HTML locais
        
        # Configuração do Selenium
        self.setup_selenium()
    
    def setup_directories(self):
        """Configura a estrutura de diretórios para salvar os arquivos."""
        os.makedirs(self.output_dir, exist_ok=True)
        os.makedirs(os.path.join(self.output_dir, 'css'), exist_ok=True)
        os.makedirs(os.path.join(self.output_dir, 'js'), exist_ok=True)
        os.makedirs(os.path.join(self.output_dir, 'images'), exist_ok=True)
        os.makedirs(os.path.join(self.output_dir, 'fonts'), exist_ok=True)
        os.makedirs(os.path.join(self.output_dir, 'pages'), exist_ok=True)
    
    def setup_selenium(self):
        """Configura o driver Selenium."""
        chrome_options = Options()
        chrome_options.add_argument("--headless")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--window-size=1920,1080")
        
        self.driver = webdriver.Chrome(options=chrome_options)
    
    def is_same_domain(self, url):
        """Verifica se a URL pertence ao mesmo domínio da URL base."""
        parsed_url = urlparse(url)
        
        if self.include_subdomains:
            # Verifica se é um subdomínio ou o mesmo domínio
            return self.base_domain in parsed_url.netloc
        else:
            # Verifica se é exatamente o mesmo domínio
            return parsed_url.netloc == self.base_domain
    
    def normalize_url(self, url):
        """Normaliza a URL removendo fragmentos e normalizando o caminho."""
        parsed = urlparse(url)
        # Remove fragmentos e normaliza o caminho
        normalized = urlunsplit((parsed.scheme, parsed.netloc, 
                                 os.path.normpath(parsed.path), 
                                 parsed.query, ''))
        return normalized
    
    def get_local_path_for_page(self, url):
        """Determina o caminho local para salvar uma página."""
        if url in self.page_map:
            return self.page_map[url]
            
        parsed = urlparse(url)
        path = parsed.path.strip('/')
        
        if not path or path.endswith('/'):
            # URL raiz ou diretório
            if url == self.base_url or not path:
                filename = 'index.html'
                self.page_map[url] = filename
                return filename  # Página inicial na raiz
            else:
                directory = path
                filename = 'index.html'
                os.makedirs(os.path.join(self.output_dir, 'pages', directory), exist_ok=True)
                local_path = os.path.join('pages', directory, filename)
                self.page_map[url] = local_path
                return local_path
        else:
            # URL com caminho específico
            if '.' in os.path.basename(path) and not path.endswith(('.html', '.htm', '.php')):
                # Provavelmente um recurso, não uma página
                directory = os.path.dirname(path)
                filename = os.path.basename(path)
                resource_type = self.determine_resource_type(filename)
                os.makedirs(os.path.join(self.output_dir, resource_type, directory), exist_ok=True)
                local_path = os.path.join(resource_type, directory, filename)
                self.page_map[url] = local_path
                return local_path
            else:
                # Página HTML
                directory = os.path.dirname(path)
                filename = os.path.basename(path)
                if not filename.endswith(('.html', '.htm')):
                    filename = f"{filename}.html"
                
                if directory:
                    os.makedirs(os.path.join(self.output_dir, 'pages', directory), exist_ok=True)
                    local_path = os.path.join('pages', directory, filename)
                else:
                    os.makedirs(os.path.join(self.output_dir, 'pages'), exist_ok=True)
                    local_path = os.path.join('pages', filename)
                
                self.page_map[url] = local_path
                return local_path
    
    def determine_resource_type(self, filename):
        """Determina o tipo de recurso com base na extensão do arquivo."""
        lower_filename = filename.lower()
        if any(lower_filename.endswith(ext) for ext in ['.css']):
            return 'css'
        elif any(lower_filename.endswith(ext) for ext in ['.js']):
            return 'js'
        elif any(lower_filename.endswith(ext) for ext in 
                ['.jpg', '.jpeg', '.png', '.gif', '.svg', '.webp', '.ico']):
            return 'images'
        elif any(lower_filename.endswith(ext) for ext in 
                ['.woff', '.woff2', '.ttf', '.eot', '.otf']):
            return 'fonts'
        else:
            return 'misc'
    
    def get_resource_filename(self, url, content_type=None):
        """Gera um nome de arquivo para um recurso."""
        parsed = urlparse(url)
        path = parsed.path.strip('/')
        
        if path and '.' in os.path.basename(path):
            # Usa o nome do arquivo da URL se disponível
            return os.path.basename(path)
        else:
            # Gera um nome baseado no hash da URL
            url_hash = hashlib.md5(url.encode()).hexdigest()[:8]
            
            # Determina a extensão com base no tipo de conteúdo
            extension = '.bin'  # Padrão
            if content_type:
                if 'text/css' in content_type:
                    extension = '.css'
                elif 'javascript' in content_type:
                    extension = '.js'
                elif 'image/jpeg' in content_type:
                    extension = '.jpg'
                elif 'image/png' in content_type:
                    extension = '.png'
                elif 'image/svg+xml' in content_type:
                    extension = '.svg'
                elif 'image/webp' in content_type:
                    extension = '.webp'
                elif 'font/' in content_type or 'application/font' in content_type:
                    extension = '.woff'
            
            return f"resource_{url_hash}{extension}"
    
    def download_resource(self, url, resource_type):
        """Baixa um recurso e retorna o caminho local."""
        if url in self.resource_map:
            return self.resource_map[url]
        
        try:
            response = requests.get(url, timeout=10)
            if response.status_code != 200:
                logger.warning(f"Erro ao baixar {url}: Status {response.status_code}")
                return None
            
            content_type = response.headers.get('Content-Type', '')
            filename = self.get_resource_filename(url, content_type)
            
            # Determina o tipo de recurso se não foi especificado
            if not resource_type:
                resource_type = self.determine_resource_type(filename)
            
            filepath = os.path.join(self.output_dir, resource_type, filename)
            
            with open(filepath, 'wb') as f:
                f.write(response.content)
            
            relative_path = os.path.join(resource_type, filename)
            self.resource_map[url] = relative_path
            logger.info(f"Baixado: {url} -> {relative_path}")
            
            return relative_path
        except Exception as e:
            logger.error(f"Erro ao baixar {url}: {str(e)}")
            return None
    
    def process_css(self, css_content, base_url):
        """Processa arquivos CSS para baixar recursos referenciados."""
        # Encontra URLs em regras CSS
        url_pattern = re.compile(r'url\([\'"]?(.*?)[\'"]?\)')
        urls = url_pattern.findall(css_content)
        
        for url in urls:
            if url.startswith('data:'):
                continue  # Ignora URLs de dados embutidos
            
            absolute_url = urljoin(base_url, url)
            
            # Determina o tipo de recurso
            if any(ext in url.lower() for ext in ['.jpg', '.jpeg', '.png', '.gif', '.svg', '.webp']):
                resource_type = 'images'
            elif any(ext in url.lower() for ext in ['.woff', '.woff2', '.ttf', '.eot', '.otf']):
                resource_type = 'fonts'
            else:
                continue  # Ignora outros tipos de recursos
            
            local_path = self.download_resource(absolute_url, resource_type)
            if local_path:
                # Substitui a URL no CSS
                css_content = css_content.replace(f'url({url})', f'url(../{local_path})')
                css_content = css_content.replace(f'url("{url}")', f'url("../{local_path}")')
                css_content = css_content.replace(f"url('{url}')", f"url('../{local_path}')")
        
        return css_content
    
    def extract_links(self, soup, current_url):
        """Extrai links de uma página para rastreamento."""
        links = []
        
        # Extrai links de âncoras
        for a_tag in soup.find_all('a', href=True):
            href = a_tag['href']
            
            # Ignora links de e-mail, telefone, etc.
            if href.startswith(('mailto:', 'tel:', 'javascript:')):
                continue
                
            # Trata links com âncoras (#)
            if href.startswith('#'):
                # Converte links de âncora para páginas específicas
                section_name = href[1:]  # Remove o # inicial
                if section_name in ['spiritual', 'holistic', 'peptide']:
                    if section_name == 'spiritual':
                        a_tag['href'] = 'pages/spiritual-awakening.html'
                    elif section_name == 'holistic':
                        a_tag['href'] = 'pages/holistic-health.html'
                    elif section_name == 'peptide':
                        a_tag['href'] = 'pages/peptide-stacking.html'
                continue
            
            absolute_url = urljoin(current_url, href)
            
            # Verifica se é do mesmo domínio
            if self.is_same_domain(absolute_url):
                normalized_url = self.normalize_url(absolute_url)
                links.append(normalized_url)
                
                # Atualiza o href para apontar para o arquivo local
                local_path = self.get_local_path_for_page(normalized_url)
                
                # Ajusta o caminho relativo com base na localização da página atual
                current_local_path = self.get_local_path_for_page(current_url)
                if current_local_path == 'index.html':
                    # Na página inicial, links para subpáginas são diretos
                    a_tag['href'] = local_path
                elif current_url != self.base_url and local_path == 'index.html':
                    # De uma subpágina para a página inicial
                    a_tag['href'] = '../index.html'
                elif current_url != self.base_url and local_path.startswith('pages/'):
                    # De uma subpágina para outra subpágina
                    a_tag['href'] = f"../{local_path}"
        
        return links
    
    def process_page(self, url):
        """Processa uma página, extraindo seu conteúdo e links."""
        if url in self.visited_urls:
            return
        
        self.visited_urls.add(url)
        logger.info(f"Processando página: {url}")
        
        try:
            self.driver.get(url)
            # Esperar que a página carregue
            time.sleep(3)
            
            # Rolar a página para garantir que todo o conteúdo seja carregado
            self.scroll_page()
            
            # Obter o HTML
            html_content = self.driver.page_source
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # Processar recursos da página
            self.process_page_resources(soup, url)
            
            # Extrair e processar links
            new_links = self.extract_links(soup, url)
            
            # Processar botões que podem ser links
            self.process_buttons(soup, url)
            
            # Salvar a página HTML
            local_path = self.get_local_path_for_page(url)
            with open(os.path.join(self.output_dir, local_path), 'w', encoding='utf-8') as f:
                f.write(str(soup))
            
            # Adicionar novos links à fila de visitas
            if len(self.visited_urls) < self.max_pages:
                for link in new_links:
                    if link not in self.visited_urls and link not in self.to_visit_urls:
                        self.to_visit_urls.append(link)
        
        except Exception as e:
            logger.error(f"Erro ao processar {url}: {str(e)}")
    
    def process_buttons(self, soup, current_url):
        """Processa botões que podem funcionar como links de navegação."""
        for button in soup.find_all('button'):
            # Verifica se o botão tem texto que indica navegação
            button_text = button.get_text().strip().lower()
            
            # Adiciona atributos para botões específicos baseados no texto
            if 'begin your journey' in button_text:
                button['onclick'] = "window.location.href='pages/spiritual-awakening.html'"
            elif 'learn more' in button_text:
                button['onclick'] = "window.location.href='pages/holistic-health.html'"
            elif 'connect' in button_text:
                button['onclick'] = "window.location.href='pages/survey.html'"
            elif 'explore peptide protocols' in button_text:
                button['onclick'] = "window.location.href='pages/peptide-stacking.html'"
            
            # Ajusta caminhos relativos para subpáginas
            if current_url != self.base_url and 'onclick' in button.attrs:
                if button['onclick'].startswith("window.location.href='pages/"):
                    button['onclick'] = button['onclick'].replace(
                        "window.location.href='pages/", 
                        "window.location.href='../"
                    )
    
    def process_page_resources(self, soup, page_url):
        """Processa e baixa recursos referenciados na página."""
        # Processar CSS
        for link in soup.find_all('link', rel='stylesheet'):
            if 'href' in link.attrs:
                css_url = urljoin(page_url, link['href'])
                try:
                    response = requests.get(css_url, timeout=10)
                    if response.status_code == 200:
                        css_content = response.text
                        processed_css = self.process_css(css_content, page_url)
                        
                        # Gerar nome de arquivo para o CSS
                        css_filename = self.get_resource_filename(css_url, 'text/css')
                        css_path = os.path.join('css', css_filename)
                        
                        # Salvar o CSS processado
                        with open(os.path.join(self.output_dir, css_path), 'w', encoding='utf-8') as f:
                            f.write(processed_css)
                        
                        # Atualizar o link no HTML
                        if page_url == self.base_url:
                            link['href'] = css_path
                        else:
                            link['href'] = f"../{css_path}"
                        
                        # Registrar no mapa de recursos
                        self.resource_map[css_url] = css_path
                except Exception as e:
                    logger.error(f"Erro ao processar CSS {css_url}: {str(e)}")
        
        # Processar scripts
        for script in soup.find_all('script', src=True):
            if 'src' in script.attrs:
                js_url = urljoin(page_url, script['src'])
                local_path = self.download_resource(js_url, 'js')
                if local_path:
                    if page_url == self.base_url:
                        script['src'] = local_path
                    else:
                        script['src'] = f"../{local_path}"
        
        # Processar imagens
        for img in soup.find_all('img', src=True):
            if 'src' in img.attrs:
                img_url = urljoin(page_url, img['src'])
                local_path = self.download_resource(img_url, 'images')
                if local_path:
                    if page_url == self.base_url:
                        img['src'] = local_path
                    else:
                        img['src'] = f"../{local_path}"
        
        # Processar estilos inline
        for style in soup.find_all('style'):
            if style.string:
                processed_css = self.process_css(style.string, page_url)
                style.string = processed_css
    
    def scroll_page(self):
        """Rola a página para garantir que todo o conteúdo seja carregado."""
        try:
            # Rolar até o final da página
            last_height = self.driver.execute_script("return document.body.scrollHeight")
            while True:
                self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                time.sleep(1)
                new_height = self.driver.execute_script("return document.body.scrollHeight")
                if new_height == last_height:
                    break
                last_height = new_height
            
            # Voltar ao topo
            self.driver.execute_script("window.scrollTo(0, 0);")
        except Exception as e:
            logger.error(f"Erro ao rolar a página: {str(e)}")
    
    def create_sitemap(self):
        """Cria um sitemap com todas as páginas visitadas."""
        sitemap_content = "<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n"
        sitemap_content += "<urlset xmlns=\"http://www.sitemaps.org/schemas/sitemap/0.9\">\n"
        
        for url in self.visited_urls:
            sitemap_content += f"  <url>\n    <loc>{url}</loc>\n  </url>\n"
        
        sitemap_content += "</urlset>"
        
        with open(os.path.join(self.output_dir, 'sitemap.xml'), 'w', encoding='utf-8') as f:
            f.write(sitemap_content)
    
    def create_robots_txt(self):
        """Cria um arquivo robots.txt básico."""
        robots_content = "User-agent: *\nAllow: /\n\n"
        robots_content += f"Sitemap: {urljoin(self.base_url, 'sitemap.xml')}"
        
        with open(os.path.join(self.output_dir, 'robots.txt'), 'w', encoding='utf-8') as f:
            f.write(robots_content)
    
    def create_subpages_index(self):
        """Cria um arquivo index.html na pasta pages com links para todas as subpáginas."""
        pages_dir = os.path.join(self.output_dir, 'pages')
        if not os.path.exists(pages_dir):
            return
        
        html_content = """<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Índice de Subpáginas</title>
    <style>
        body {
            font-family: Arial, sans-serif;
            max-width: 800px;
            margin: 0 auto;
            padding: 20px;
        }
        h1 {
            color: #333;
            border-bottom: 1px solid #eee;
            padding-bottom: 10px;
        }
        ul {
            list-style-type: none;
            padding: 0;
        }
        li {
            margin: 10px 0;
            padding: 10px;
            background-color: #f9f9f9;
            border-radius: 4px;
        }
        a {
            color: #0066cc;
            text-decoration: none;
        }
        a:hover {
            text-decoration: underline;
        }
        .back-link {
            display: inline-block;
            margin-top: 20px;
            padding: 10px 15px;
            background-color: #0066cc;
            color: white;
            border-radius: 4px;
            text-decoration: none;
        }
        .back-link:hover {
            background-color: #0052a3;
        }
    </style>
</head>
<body>
    <h1>Índice de Subpáginas</h1>
    <ul>
"""
        
        # Adicionar links para todas as páginas visitadas (exceto a página inicial)
        for url in sorted(self.visited_urls):
            if url != self.base_url:
                local_path = self.get_local_path_for_page(url)
                if local_path.startswith('pages/'):
                    relative_path = local_path[6:]  # Remove 'pages/' prefix
                    html_content += f'        <li><a href="{relative_path}">{url}</a></li>\n'
        
        html_content += """    </ul>
    <a href="../index.html" class="back-link">Voltar para a Página Inicial</a>
</body>
</html>
"""
        
        with open(os.path.join(pages_dir, 'index.html'), 'w', encoding='utf-8') as f:
            f.write(html_content)
    
    def create_button_fix_js(self):
        """Cria o script JavaScript para corrigir a funcionalidade dos botões."""
        button_fix_js = """/**
 * Script para corrigir a funcionalidade dos botões no site extraído
 * Este script deve ser adicionado a todas as páginas HTML
 */

document.addEventListener('DOMContentLoaded', function() {
  // Função para configurar os botões principais
  function setupMainButtons() {
    // Botão "Begin Your Journey"
    const beginJourneyButtons = Array.from(document.querySelectorAll('button')).filter(
      btn => btn.textContent.trim() === 'Begin Your Journey'
    );
    
    beginJourneyButtons.forEach(button => {
      button.addEventListener('click', function(e) {
        e.preventDefault();
        const isSubpage = window.location.pathname.includes('/spiritual-awakening') || 
                         window.location.pathname.includes('/pages/');
        const targetPath = isSubpage ? '../pages/spiritual-awakening.html' : 'pages/spiritual-awakening.html';
        window.location.href = targetPath;
      });
    });
    
    // Botão "Learn More"
    const learnMoreButtons = Array.from(document.querySelectorAll('button')).filter(
      btn => btn.textContent.trim() === 'Learn More'
    );
    
    learnMoreButtons.forEach(button => {
      button.addEventListener('click', function(e) {
        e.preventDefault();
        const isSubpage = window.location.pathname.includes('/holistic-health') || 
                         window.location.pathname.includes('/pages/');
        const targetPath = isSubpage ? '../pages/holistic-health.html' : 'pages/holistic-health.html';
        window.location.href = targetPath;
      });
    });
    
    // Botão "Connect"
    const connectButtons = Array.from(document.querySelectorAll('button')).filter(
      btn => btn.textContent.trim() === 'Connect'
    );
    
    connectButtons.forEach(button => {
      button.addEventListener('click', function(e) {
        e.preventDefault();
        const isSubpage = window.location.pathname.includes('/survey') || 
                         window.location.pathname.includes('/pages/');
        const targetPath = isSubpage ? '../pages/survey.html' : 'pages/survey.html';
        window.location.href = targetPath;
      });
    });
    
    // Botão "Explore Peptide Protocols"
    const exploreButtons = Array.from(document.querySelectorAll('button')).filter(
      btn => btn.textContent.trim() === 'Explore Peptide Protocols'
    );
    
    exploreButtons.forEach(button => {
      button.addEventListener('click', function(e) {
        e.preventDefault();
        const isSubpage = window.location.pathname.includes('/peptide-stacking') || 
                         window.location.pathname.includes('/pages/');
        const targetPath = isSubpage ? '../pages/peptide-stacking.html' : 'pages/peptide-stacking.html';
        window.location.href = targetPath;
      });
    });
    
    // Botão "Schedule a Consultation"
    const scheduleButtons = Array.from(document.querySelectorAll('button')).filter(
      btn => btn.textContent.trim() === 'Schedule a Consultation'
    );
    
    scheduleButtons.forEach(button => {
      button.addEventListener('click', function(e) {
        e.preventDefault();
        const isSubpage = window.location.pathname.includes('/survey') || 
                         window.location.pathname.includes('/pages/');
        const targetPath = isSubpage ? '../pages/survey.html' : 'pages/survey.html';
        window.location.href = targetPath;
      });
    });
  }
  
  // Função para configurar os botões de navegação do carrossel
  function setupCarouselButtons() {
    // Botões "Previous slide" e "Next slide"
    const prevButtons = Array.from(document.querySelectorAll('button')).filter(
      btn => btn.textContent.includes('Previous slide')
    );
    
    const nextButtons = Array.from(document.querySelectorAll('button')).filter(
      btn => btn.textContent.includes('Next slide')
    );
    
    // Implementação simples de carrossel
    if (prevButtons.length > 0 && nextButtons.length > 0) {
      // Encontrar os elementos do carrossel
      const carouselItems = document.querySelectorAll('.carousel-item, [role="region"] > div');
      
      if (carouselItems.length > 0) {
        let currentIndex = 0;
        
        // Função para mostrar apenas o item atual
        function updateCarousel() {
          carouselItems.forEach((item, index) => {
            if (index === currentIndex) {
              item.style.display = 'block';
            } else {
              item.style.display = 'none';
            }
          });
          
          // Atualizar estado dos botões
          if (currentIndex === 0) {
            prevButtons.forEach(btn => btn.setAttribute('disabled', ''));
          } else {
            prevButtons.forEach(btn => btn.removeAttribute('disabled'));
          }
          
          if (currentIndex === carouselItems.length - 1) {
            nextButtons.forEach(btn => btn.setAttribute('disabled', ''));
          } else {
            nextButtons.forEach(btn => btn.removeAttribute('disabled'));
          }
        }
        
        // Configurar botões
        prevButtons.forEach(button => {
          button.addEventListener('click', function() {
            if (currentIndex > 0) {
              currentIndex--;
              updateCarousel();
            }
          });
        });
        
        nextButtons.forEach(button => {
          button.addEventListener('click', function() {
            if (currentIndex < carouselItems.length - 1) {
              currentIndex++;
              updateCarousel();
            }
          });
        });
        
        // Inicializar carrossel
        updateCarousel();
      }
    }
  }
  
  // Função para corrigir links relativos
  function fixRelativeLinks() {
    // Obtém o caminho atual
    var currentPath = window.location.pathname;
    var isSubpage = currentPath.includes('/pages/');
    
    // Corrige links de navegação
    document.querySelectorAll('a').forEach(function(link) {
      var href = link.getAttribute('href');
      if (!href) return;
      
      // Ignora links externos e links de email/telefone
      if (href.startsWith('http') || href.startsWith('mailto:') || href.startsWith('tel:')) return;
      
      // Corrige links para a página inicial
      if (href === '/' || href === '') {
        link.setAttribute('href', isSubpage ? '../index.html' : 'index.html');
      }
      
      // Corrige links para subpáginas
      if (href.startsWith('/') && !href.startsWith('/pages/')) {
        var pageName = href.substring(1);
        if (!pageName.endsWith('.html')) pageName += '.html';
        link.setAttribute('href', isSubpage ? '../pages/' + pageName : 'pages/' + pageName);
      }
      
      // Corrige links de âncora para seções específicas
      if (href.startsWith('/#')) {
        var section = href.substring(2);
        var targetPage = '';
        
        if (section === 'spiritual') {
          targetPage = 'spiritual-awakening.html';
        } else if (section === 'holistic') {
          targetPage = 'holistic-health.html';
        } else if (section === 'peptide') {
          targetPage = 'peptide-stacking.html';
        }
        
        if (targetPage) {
          link.setAttribute('href', isSubpage ? targetPage : 'pages/' + targetPage);
        }
      }
    });
  }
  
  // Executar todas as funções de correção
  setupMainButtons();
  setupCarouselButtons();
  fixRelativeLinks();
  
  console.log('Button functionality fix applied successfully!');
});"""
        
        # Salvar o script na raiz do site
        with open(os.path.join(self.output_dir, 'button_fix.js'), 'w', encoding='utf-8') as f:
            f.write(button_fix_js)
        
        # Salvar o script também na pasta pages
        with open(os.path.join(self.output_dir, 'pages', 'button_fix.js'), 'w', encoding='utf-8') as f:
            f.write(button_fix_js)
    
    def add_button_fix_to_html(self):
        """Adiciona o script button_fix.js a todos os arquivos HTML."""
        # Adicionar à página principal
        index_path = os.path.join(self.output_dir, 'index.html')
        if os.path.exists(index_path):
            with open(index_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            if '</body>' in content and 'button_fix.js' not in content:
                content = content.replace('</body>', '<script src="button_fix.js"></script></body>')
                
                with open(index_path, 'w', encoding='utf-8') as f:
                    f.write(content)
        
        # Adicionar às subpáginas
        pages_dir = os.path.join(self.output_dir, 'pages')
        if os.path.exists(pages_dir):
            for file in os.listdir(pages_dir):
                if file.endswith('.html'):
                    file_path = os.path.join(pages_dir, file)
                    
                    with open(file_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                    
                    if '</body>' in content and 'button_fix.js' not in content:
                        content = content.replace('</body>', '<script src="../button_fix.js"></script></body>')
                        
                        with open(file_path, 'w', encoding='utf-8') as f:
                            f.write(content)
    
    def fix_navigation_links(self):
        """Corrige links de navegação em todas as páginas HTML."""
        # Mapeia padrões de URL para arquivos locais
        url_patterns = {
            'href="/"': 'href="index.html"',
            'href="/index.html"': 'href="index.html"',
            'href="/#spiritual"': 'href="pages/spiritual-awakening.html"',
            'href="/#holistic"': 'href="pages/holistic-health.html"',
            'href="/#peptide"': 'href="pages/peptide-stacking.html"',
            'href="/spiritual-awakening"': 'href="pages/spiritual-awakening.html"',
            'href="/holistic-health"': 'href="pages/holistic-health.html"',
            'href="/peptide-stacking"': 'href="pages/peptide-stacking.html"',
            'href="/survey"': 'href="pages/survey.html"',
        }
        
        # Padrões para subpáginas (com caminhos relativos diferentes)
        subpage_patterns = {
            'href="/"': 'href="../index.html"',
            'href="/index.html"': 'href="../index.html"',
            'href="/#spiritual"': 'href="spiritual-awakening.html"',
            'href="/#holistic"': 'href="holistic-health.html"',
            'href="/#peptide"': 'href="peptide-stacking.html"',
            'href="/spiritual-awakening"': 'href="spiritual-awakening.html"',
            'href="/holistic-health"': 'href="holistic-health.html"',
            'href="/peptide-stacking"': 'href="peptide-stacking.html"',
            'href="/survey"': 'href="survey.html"',
        }
        
        # Corrige links na página principal
        index_path = os.path.join(self.output_dir, 'index.html')
        if os.path.exists(index_path):
            with open(index_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            for pattern, replacement in url_patterns.items():
                content = content.replace(pattern, replacement)
            
            with open(index_path, 'w', encoding='utf-8') as f:
                f.write(content)
        
        # Corrige links nas subpáginas
        pages_dir = os.path.join(self.output_dir, 'pages')
        if os.path.exists(pages_dir):
            for file in os.listdir(pages_dir):
                if file.endswith('.html'):
                    file_path = os.path.join(pages_dir, file)
                    
                    with open(file_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                    
                    for pattern, replacement in subpage_patterns.items():
                        content = content.replace(pattern, replacement)
                    
                    with open(file_path, 'w', encoding='utf-8') as f:
                        f.write(content)
    
    def create_zip_archive(self):
        """Cria um arquivo ZIP com todo o conteúdo do site extraído."""
        zip_filename = f"{os.path.basename(self.output_dir)}.zip"
        zip_path = os.path.join(os.path.dirname(self.output_dir), zip_filename)
        
        # Remover arquivo ZIP existente, se houver
        if os.path.exists(zip_path):
            os.remove(zip_path)
        
        # Criar arquivo ZIP
        shutil.make_archive(
            os.path.splitext(zip_path)[0],  # Nome base (sem extensão)
            'zip',                          # Formato
            self.output_dir                 # Diretório raiz
        )
        
        logger.info(f"Arquivo ZIP criado: {zip_path}")
        return zip_path
    
    def remove_lovable_references(self):
        """Remove referências a 'Lovable' de todos os arquivos HTML.
        
        Esta função automatiza as alterações manuais identificadas no repositório
        gilded-awakening-focus-clean, removendo badges e referências a 'Lovable'
        de todos os arquivos HTML.
        """
        logger.info("Removendo referências a 'Lovable' de todos os arquivos HTML...")
        
        # Lista de arquivos HTML para processar
        html_files = []
        
        # Adicionar arquivo index.html
        index_path = os.path.join(self.output_dir, 'index.html')
        if os.path.exists(index_path):
            html_files.append(index_path)
        
        # Adicionar arquivos HTML da pasta pages
        pages_dir = os.path.join(self.output_dir, 'pages')
        if os.path.exists(pages_dir):
            for file in os.listdir(pages_dir):
                if file.endswith('.html'):
                    html_files.append(os.path.join(pages_dir, file))
        
        # Processar cada arquivo HTML
        for file_path in html_files:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                # Remover referências a 'Lovable' no conteúdo
                # 1. Substituir 'Lovable' por '' em classes, IDs e textos
                content = re.sub(r'Lovable\s+', '', content)
                content = re.sub(r'\s+Lovable', '', content)
                
                # 2. Substituir 'Lovable' por '' em footer e header
                content = content.replace('class="footer-logo">Lovable', 'class="footer-logo">Focus')
                content = content.replace('class="header-logo">Lovable', 'class="header-logo">Focus')
                
                # 3. Substituir copyright
                content = re.sub(r'© 2025 Lovable\.', '© 2025 Focus.', content)
                
                # 4. Remover badges ou elementos com classe que contém 'lovable'
                soup = BeautifulSoup(content, 'html.parser')
                
                # Remover elementos com classe que contém 'lovable'
                for element in soup.find_all(class_=lambda c: c and 'lovable' in c.lower()):
                    element.decompose()
                
                # Remover elementos com id que contém 'lovable'
                for element in soup.find_all(id=lambda i: i and 'lovable' in i.lower()):
                    element.decompose()
                
                # Salvar o conteúdo modificado
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(str(soup))
                
                logger.info(f"Referências a 'Lovable' removidas de: {file_path}")
            
            except Exception as e:
                logger.error(f"Erro ao processar {file_path}: {str(e)}")
    
    def simplify_readme(self):
        """Simplifica o README removendo seções desnecessárias.
        
        Esta função automatiza as alterações manuais identificadas no repositório
        gilded-awakening-focus-clean, simplificando o README.md.
        """
        readme_path = os.path.join(self.output_dir, 'README.md')
        
        # Verificar se o README existe
        if not os.path.exists(readme_path):
            # Criar um README simplificado
            simple_readme = f"""# Focus Website

Este é o site extraído de Focus, com navegação funcional e recursos completos.

## Conteúdo

- Página inicial
- Páginas de conteúdo
- Recursos (CSS, JavaScript, imagens)
- Navegação funcional

## Como usar

Abra o arquivo `index.html` em um navegador para visualizar o site.
"""
            
            with open(readme_path, 'w', encoding='utf-8') as f:
                f.write(simple_readme)
            
            logger.info(f"README simplificado criado: {readme_path}")
        else:
            # Simplificar o README existente
            try:
                with open(readme_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                # Substituir referências a 'Lovable' por 'Focus'
                content = content.replace('Lovable', 'Focus')
                
                # Simplificar o conteúdo
                lines = content.split('\n')
                simplified_lines = []
                
                # Manter apenas as seções importantes
                in_important_section = True
                for line in lines:
                    if line.startswith('## '):
                        # Verificar se é uma seção importante
                        section_name = line[3:].lower()
                        in_important_section = section_name in ['conteúdo', 'content', 'como usar', 'how to use']
                    
                    if in_important_section:
                        simplified_lines.append(line)
                
                # Se ficou muito curto, adicionar conteúdo padrão
                if len(simplified_lines) < 10:
                    simplified_lines = [
                        "# Focus Website",
                        "",
                        "Este é o site extraído de Focus, com navegação funcional e recursos completos.",
                        "",
                        "## Conteúdo",
                        "",
                        "- Página inicial",
                        "- Páginas de conteúdo",
                        "- Recursos (CSS, JavaScript, imagens)",
                        "- Navegação funcional",
                        "",
                        "## Como usar",
                        "",
                        "Abra o arquivo `index.html` em um navegador para visualizar o site."
                    ]
                
                # Salvar o README simplificado
                with open(readme_path, 'w', encoding='utf-8') as f:
                    f.write('\n'.join(simplified_lines))
                
                logger.info(f"README simplificado: {readme_path}")
            
            except Exception as e:
                logger.error(f"Erro ao simplificar README: {str(e)}")
    
    def run(self):
        """Executa o processo de scraping completo."""
        try:
            while self.to_visit_urls and len(self.visited_urls) < self.max_pages:
                current_url = self.to_visit_urls.pop(0)
                if current_url not in self.visited_urls:
                    self.process_page(current_url)
            
            # Criar script para corrigir botões
            self.create_button_fix_js()
            
            # Adicionar script a todos os arquivos HTML
            self.add_button_fix_to_html()
            
            # Corrigir links de navegação
            self.fix_navigation_links()
            
            # Criar arquivos adicionais
            self.create_sitemap()
            self.create_robots_txt()
            self.create_subpages_index()
            
            # Aplicar limpeza automática (remoção de referências a 'Lovable')
            self.remove_lovable_references()
            
            # Simplificar README
            self.simplify_readme()
            
            # Criar arquivo ZIP
            zip_path = self.create_zip_archive()
            
            logger.info(f"Scraping concluído! Páginas processadas: {len(self.visited_urls)}")
            logger.info(f"Arquivos salvos em: {os.path.abspath(self.output_dir)}")
            logger.info(f"Arquivo ZIP criado: {zip_path}")
            
            return {
                'output_dir': os.path.abspath(self.output_dir),
                'zip_path': zip_path,
                'pages_processed': len(self.visited_urls)
            }
        
        finally:
            self.driver.quit()

def main():
    parser = argparse.ArgumentParser(description='Extrai o código HTML, CSS e JavaScript de um site, incluindo subpáginas, com navegação funcional.')
    parser.add_argument('url', help='URL do site para extrair')
    parser.add_argument('--output', '-o', default='extracted_site', help='Diretório de saída para os arquivos extraídos')
    parser.add_argument('--max-pages', '-m', type=int, default=20, help='Número máximo de páginas para extrair')
    parser.add_argument('--include-subdomains', '-s', action='store_true', help='Incluir subdomínios no scraping')
    parser.add_argument('--create-zip', '-z', action='store_true', help='Criar arquivo ZIP com o site extraído')
    parser.add_argument('--clean-lovable', '-c', action='store_true', help='Remover referências a "Lovable" de todos os arquivos HTML')
    parser.add_argument('--simplify-readme', '-r', action='store_true', help='Simplificar o README removendo seções desnecessárias')
    
    args = parser.parse_args()
    
    scraper = WebsiteScraper(
        base_url=args.url,
        output_dir=args.output,
        max_pages=args.max_pages,
        include_subdomains=args.include_subdomains
    )
    
    result = scraper.run()
    
    print("\nResumo da extração:")
    print(f"- Páginas processadas: {result['pages_processed']}")
    print(f"- Diretório de saída: {result['output_dir']}")
    print(f"- Arquivo ZIP: {result['zip_path']}")
    print("\nO site extraído está pronto para ser hospedado em qualquer plataforma!")

if __name__ == "__main__":
    main()
